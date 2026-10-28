from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
import bcrypt
import pyotp
import base64
from cryptography.fernet import Fernet
from functools import wraps

app = Flask(__name__) 
app.secret_key = 'tu_llave_secreta_muy_seguraa'

# --- CONFIGURACIÓN DE CIFRADO ---

FERNET_KEY = b'OWse9V6IYLnD3CKlwmqp0Yta0ALUGrlONFx3GGtRXDg='
cipher_suite = Fernet(FERNET_KEY)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'sistema_clinico'
}

def get_db():
    return mysql.connector.connect(**db_config)

# --- PROTECTOR DE RUTAS (MIDDLEWARE) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE NAVEGACIÓN PRINCIPAL ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# --- PANEL DE ADMINISTRACIÓN (CORREGIDO) ---
# RUTA 1: Solo carga el diseño del HTML (El JS se encarga del resto)
@app.route('/admin')
def admin_panel():
    return render_template('admin.html')



# RUTA 2: La que el JavaScript busca para llenar la tabla (La que faltaba)
@app.route('/admin/users')
def get_users_json():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Consultamos solo los campos que existen
        cursor.execute("SELECT id, nombre, ap_paterno, usuario, rol, correo, esta_aprobado FROM empleados")
        usuarios = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Devolvemos SOLO la lista de usuarios. 
        # Esto hace que users.forEach() en tu JS funcione de nuevo.
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/approve/<int:id>', methods=['POST'])
def approve_user(id):
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Ejecutamos la actualización del estado
        cursor.execute("UPDATE empleados SET esta_aprobado = 1 WHERE id = %s", (id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Devolvemos éxito para que el JavaScript recargue la tabla
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error al aprobar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- DASHBOARD DE MÉDICOS / PERSONAL ---
@app.route('/bd')
@login_required
def dashboard():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Obtener expedientes para la tabla principal
        cursor.execute("SELECT * FROM expedientes ORDER BY fecha_registro DESC")
        expedientes = cursor.fetchall()
        
        # 2. Obtener personal de la tabla 'empleados' para los selectores del modal
        # Solo traemos a los que ya fueron aprobados por el admin
        cursor.execute("SELECT id, nombre, ap_paterno, rol FROM empleados WHERE esta_aprobado = 1")
        lista_personal = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # IMPORTANTE: Pasamos 'personal=lista_personal' para que el HTML lo reconozca
        return render_template('bd.html', expedientes=expedientes, personal=lista_personal)
    except Exception as e:
        return f"Error en Dashboard: {str(e)}", 500

# --- AUTENTICACIÓN (LOGIN Y REGISTRO) ---
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        password_hash = bcrypt.hashpw(data.get('password').encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        otp_secret = pyotp.random_base32()

        conn = get_db()
        cursor = conn.cursor()
        query = """INSERT INTO empleados (nombre, ap_paterno, ap_materno, correo, usuario, rol, password_hash, otp_secret, esta_aprobado) 
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)"""
        cursor.execute(query, (data.get('names'), data.get('pat'), data.get('mat'), 
                               data.get('email'), data.get('username'), data.get('role'), 
                               password_hash, otp_secret))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "otp_secret": otp_secret})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    otp_code = request.form.get('otp_code')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados WHERE usuario = %s", (username,))
    user = cursor.fetchone()
    conn.close()

    # 1. Validamos si el usuario existe y la contraseña es correcta
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        
        # 2. Validamos el código 2FA
        totp = pyotp.TOTP(user['otp_secret'])
        if totp.verify(otp_code):
            
            # 3. Validamos si está aprobado
            # Cambiamos a 'error' para que el JS use el modal rojo con el mensaje
            if user['esta_aprobado'] == 0:
                return jsonify({
                    "status": "error", 
                    "message": "ACCESO RESTRINGIDO: Tu cuenta aún no ha sido validada por el administrador de ClinicaSecure."
                })
            
            # 4. Éxito: Iniciar Sesión
            session['user_id'] = user['id']
            session['nombre_completo'] = f"{user['nombre']} {user['ap_paterno']}"
            session['otp_secret'] = user['otp_secret']
            session['rol'] = user['rol']
            
            return jsonify({"status": "success", "redirect": url_for('dashboard')})
        
        else:
            # Error en el código TOTP
            return jsonify({"status": "error", "message": "El código 2FA es inválido o ha expirado. Intenta de nuevo."})
            
    # Error en credenciales
    return jsonify({"status": "error", "message": "Usuario o contraseña incorrectos. Verifica tus datos de auditoría."})
# --- GESTIÓN DE EXPEDIENTES (CIFRADO Y ABAC) ---
@app.route('/guardar_expediente', methods=['POST'])
def guardar_expediente():
    # 1. Recoger datos del formulario
    nombre = request.form.get('nombre')
    nss = request.form.get('nss')
    edad = request.form.get('edad')
    sangre = request.form.get('sangre')
    diagnostico_plano = request.form.get('diagnostico')
    diagnostico_cifrado = cipher_suite.encrypt(diagnostico_plano.encode()).decode()
    doctor_id = request.form.get('doctor_id')
    enfermera_id = request.form.get('enfermera_id')

    # 2. Obtener nombres para evitar consultas extra (Denormalización útil aquí)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Buscamos nombre del Dr.
    cursor.execute("SELECT nombre, ap_paterno FROM empleados WHERE id = %s", (doctor_id,))
    doc = cursor.fetchone()
    nombre_doc = f"{doc['nombre']} {doc['ap_paterno']}"

    # Buscamos nombre de la Enfermera
    cursor.execute("SELECT nombre, ap_paterno FROM empleados WHERE id = %s", (enfermera_id,))
    enf = cursor.fetchone()
    nombre_enf = f"{enf['nombre']} {enf['ap_paterno']}"

    # 3. Aquí iría tu lógica de CIFRADO para el diagnóstico_plano
    # diagnostico_cifrado = cifrar_aes(diagnostico_plano) 

    # 4. Insertar en la base de datos
    query = """
        INSERT INTO expedientes 
        (nombre_paciente, nss, edad, tipo_sangre, diagnostico, doctor_id, nombre_doctor, enfermera_id, nombre_enfermera, actualizado_por) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    valores = (nombre, nss, edad, sangre, diagnostico_cifrado, doctor_id, nombre_doc, enfermera_id, nombre_enf, f"Registro: {session['nombre_completo']}")
    
    cursor.execute(query, valores)
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/ver_detalle/<int:id>')
@login_required
def ver_detalle(id):
    # Recuperamos el parámetro de éxito del 2FA
    auth = request.args.get('auth')
    if auth != 'success':
        return render_template('404.html') # O tu página de prohibido

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expedientes WHERE id = %s", (id,))
    paciente = cursor.fetchone()
    
    if not paciente:
        conn.close()
        return render_template('404.html'), 404

    # --- LÓGICA ABAC MULTI-ROL ---
    user_id = int(session['user_id'])
    es_doctor = (user_id == int(paciente['doctor_id']))
    es_enfermera = (user_id == int(paciente['enfermera_id']))
    es_admin = (session.get('rol') == 'Administrador')

    # Si NO es el doctor, NI la enfermera, NI el admin, entonces PROHIBIDO
    if not (es_doctor or es_enfermera or es_admin):
        conn.close()
        return "<h1>Acceso Prohibido: No tienes permisos para este expediente</h1>", 403

    # --- LÓGICA DE DESCIFRADO ---
    diag_db = paciente['diagnostico']
    try:
        diag_real = cipher_suite.decrypt(diag_db.encode()).decode()
    except Exception:
        diag_real = diag_db 

    cursor.close()
    conn.close()
    return render_template('detalle.html', p=paciente, diag_descifrado=diag_real, actualizaciones=[])
# --- MANEJO DE ERRORES ---
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

from datetime import datetime # Asegúrate de tener esta importación arriba

@app.route('/agregar_actualizacion/<int:id>', methods=['POST'])
@login_required
def agregar_actualizacion(id):
    nueva_nota = request.form.get('contenido')
    if not nueva_nota:
        return redirect(url_for('ver_detalle', id=id))

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Traemos el diagnóstico actual
        cursor.execute("SELECT diagnostico FROM expedientes WHERE id = %s", (id,))
        registro = cursor.fetchone()
        
        # 2. Intentamos descifrar lo que ya existe
        try:
            contenido_viejo = cipher_suite.decrypt(registro['diagnostico'].encode()).decode()
        except:
            contenido_viejo = registro['diagnostico'] # Si era texto plano, lo dejamos así

        # 3. Creamos el nuevo bloque con historial
        fecha_hoy = datetime.now().strftime('%d/%m/%Y %H:%M')
        nombre_medico = session.get('nombre_completo', 'Médico')
        historial_nuevo = f"{contenido_viejo}\n\n[Actualización {fecha_hoy} - {nombre_medico}]:\n{nueva_nota}"

        # 4. Ciframos el nuevo bloque completo
        contenido_cifrado = cipher_suite.encrypt(historial_nuevo.encode()).decode()
        
        # 5. Guardamos en la tabla 'expedientes' 
        query = """
            UPDATE expedientes 
            SET diagnostico = %s, 
                ultima_actualizacion = NOW(), 
                actualizado_por = %s 
            WHERE id = %s
        """
        cursor.execute(query, (contenido_cifrado, f"Dr. {nombre_medico}", id))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error al guardar nota: {e}")
        
    return redirect(url_for('ver_detalle', id=id, auth='success'))
@app.route('/api/desbloquear_expediente/<int:id>', methods=['POST'])
@login_required
def api_desbloquear(id):
    data = request.get_json()
    codigo = data.get('codigo')
    otp_secret = session.get('otp_secret')

    if not otp_secret:
        return jsonify({"error": "Sesión inválida"}), 401

    # Validación TOTP
    try:
        totp = pyotp.TOTP(otp_secret.strip().upper())
        if not totp.verify(codigo, valid_window=1):
            return jsonify({"error": "Código incorrecto"}), 403
    except Exception as e:
        return jsonify({"error": "Error en validación 2FA"}), 500

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # CONSULTA 1: Verifica si la tabla se llama 'expedientes'
        cursor.execute("SELECT * FROM expedientes WHERE id = %s", (id,))
        p = cursor.fetchone()
        
        if not p:
            return jsonify({"error": "Expediente no encontrado"}), 404

        # Validación de permisos (ABAC)
        user_id = int(session.get('user_id', 0))
        rol = session.get('rol')
        
        # USA .get() PARA EVITAR PROGRAMMING ERROR SI LA COLUMNA NO EXISTE
        id_doc_db = p.get('doctor_id') or p.get('id_doctor') # Intenta ambos nombres comunes
        id_enf_db = p.get('enfermera_id') or p.get('id_enfermera')

        es_responsable = (user_id == id_doc_db or user_id == id_enf_db or rol == 'Administrador')

        if not es_responsable:
            return jsonify({"error": "No autorizado"}), 403

        # Descifrado
        diag_db = p.get('diagnostico', '')
        try:
            diag = cipher_suite.decrypt(diag_db.encode()).decode() if diag_db else ""
        except:
            diag = diag_db

        # CONSULTA 2: 
        # Verifica que la tabla se llame 'actualizaciones_expediente' 
        # y que la columna sea 'expediente_id'
        try:
            cursor.execute("SELECT * FROM actualizaciones_expediente WHERE expediente_id = %s", (id,))
            acts = cursor.fetchall()
        except:
            # Si la tabla de actualizaciones falla, enviamos lista vacía para no romper todo
            print("AVISO: Falló la consulta de actualizaciones. Revisa el nombre de la tabla.")
            acts = []
        
        actualizaciones = []
        for a in acts:
            contenido_db = a.get('contenido_cifrado') or a.get('contenido', '')
            try:
                contenido = cipher_suite.decrypt(contenido_db.encode()).decode()
            except:
                contenido = contenido_db

            actualizaciones.append({
                "fecha": a['fecha'].strftime('%d/%m/%Y %H:%M') if a.get('fecha') else "N/A",
                "autor": a.get('autor_nombre') or "Médico",
                "contenido": contenido
            })
            
        return jsonify({
            "status": "success",
            "diagnostico": diag,
            "actualizaciones": actualizaciones
        })

    except Exception as e:
      
        print("\n--- DETALLE DEL ERROR DE SQL ---")
        print(f"Error: {e}")
        return jsonify({"error": f"Error de base de datos: {str(e)}"}), 500
    finally:
        conn.close()
if __name__ == '__main__':
    app.run(debug=True)