/*=============== FUNCIONES GLOBALES (FUERA DEL DOM PARA QUE EL HTML LAS VEA) ===============*/

function closeAdminModal() {
    const adminModal = document.getElementById('adminModal');
    if (adminModal) {
        adminModal.style.display = 'none';
    }
}
function checkAdminAccess() {
    const user = document.getElementById('adminUser').value;
    const pass = document.getElementById('adminPass').value;

    const USER_MASTER = "admin"; 
    const PASS_MASTER = "buap2026"; 

    if (user === USER_MASTER && pass === PASS_MASTER) {
        window.location.href = '/admin'; 
    } else {
        const customAlert = document.getElementById('customAlert');
        const alertContent = customAlert.querySelector('.modal-content');
        
        // CAMBIAMOS TODO EL CONTENIDO DEL MODAL PARA EL ERROR
        alertContent.innerHTML = `
            <div class="modal-icon" style="background: #e74c3c;">×</div>
            <h2 style="color: #c0392b;">Acceso Fallido</h2>
            <div id="alertMessage">
                <div style="color: #721c24; background: #f8d7da; padding: 15px; border-radius: 8px; border: 1px solid #f5c6cb; margin-top: 15px;">
                    <i class="ri-error-warning-line" style="font-size: 2rem;"></i>
                    <p><strong>ACCESO DENEGADO</strong></p>
                    <p>Las credenciales no coinciden con el registro de auditoría.</p>
                </div>
            </div>
            <button onclick="location.reload()" class="modal-btn">Reintentar</button>
        `;

        // Cambiamos el color de la barrita superior del modal a rojo
        alertContent.style.borderTop = "10px solid #e74c3c";
        
        customAlert.style.display = 'flex';
        closeAdminModal();
    }
}

// Función global para cerrar el alert
window.closeAlertAndRedirect = () => {
    const alertModal = document.getElementById('customAlert');
    const loginAccessRegister = document.getElementById('loginAccessRegister');
    
    if (alertModal) alertModal.style.display = 'none';
    if (loginAccessRegister) {
        loginAccessRegister.classList.remove('active');
    }
};


/*=============== TODO LO DEMÁS DENTRO DEL DOMCONTENTLOADED ===============*/

document.addEventListener('DOMContentLoaded', () => {
    /*=============== FUNCIONALIDAD VER/OCULTAR CONTRASEÑA ===============*/
    const setupPasswordToggle = (inputId, eyeId) => {
        const input = document.getElementById(inputId),
              iconEye = document.getElementById(eyeId)

        if (input && iconEye) {
            iconEye.addEventListener('click', () => {
                input.type = input.type === 'password' ? 'text' : 'password'
                iconEye.classList.toggle('ri-eye-fill')
                iconEye.classList.toggle('ri-eye-off-fill')
            })
        }
    }

    setupPasswordToggle('password', 'loginPassword')
    setupPasswordToggle('passwordCreate', 'loginPasswordCreate')

    /*=============== ABRIR MODAL ADMIN ===============*/
    const adminBtn = document.getElementById('adminAccessBtn');
    const adminModal = document.getElementById('adminModal');

    if(adminBtn && adminModal) {
        adminBtn.addEventListener('click', () => {
            adminModal.style.display = 'flex';
        });
    }

    /*=============== INTERCAMBIO LOGIN & REGISTRO ===============*/
    const loginAccessRegister = document.getElementById('loginAccessRegister'),
          buttonRegister = document.getElementById('loginButtonRegister'),
          buttonAccess = document.getElementById('loginButtonAccess')

    if (buttonRegister && buttonAccess && loginAccessRegister) {
        buttonRegister.addEventListener('click', () => {
            loginAccessRegister.classList.add('active')
        })

        buttonAccess.addEventListener('click', () => {
            loginAccessRegister.classList.remove('active')
        })
    }

    /*=============== BLOQUEO DE NÚMEROS ===============*/
    const inputsLetras = document.querySelectorAll('.only-letters');
    inputsLetras.forEach(input => {
        input.addEventListener('beforeinput', (e) => {
            if (e.data && !/^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$/.test(e.data)) {
                e.preventDefault();
            }
        });
        input.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[0-9]/g, '');
        });
    });

    

    /*=============== INTEGRACIÓN CON EL BACKEND ===============*/
    const loginForm = document.getElementById('formLogin');
    const registerForm = document.getElementById('formRegister');

  const handleFormSubmit = async (e, endpoint) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();

        if (result.status === 'success') {
    if (endpoint === '/register') {
        const customAlert = document.getElementById('customAlert');
        const alertContent = customAlert.querySelector('.modal-content');

        // REESCRIBIMOS TODO EL CONTENIDO PARA QUE SEA VERDE (ÉXITO)
        alertContent.innerHTML = `
            <div class="modal-icon" style="background: #2ecc71;">✓</div>
            <h2 style="color: #27ae60;">Registro Exitoso</h2>
            <div id="alertMessage">
                <p style="color: #333;">Cuenta creada correctamente.</p>
                <div style="background: #f0fdf4; border: 2px dashed #28a745; padding: 15px; border-radius: 8px; margin: 15px 0; width: 100%; box-sizing: border-box;">
                    <small style="display:block; color: #155724; margin-bottom: 5px; font-weight: bold;">TU CÓDIGO 2FA:</small>
                    <strong style="font-size: 1.2rem; color: #155724; font-family: monospace; display: block; word-break: break-all;">${result.otp_secret}</strong>
                </div>
                <p style="font-size: 0.85rem; color: #666;">Cópialo en Google Authenticator para poder iniciar sesión.</p>
            </div>
            <button onclick="closeAlertAndRedirect()" class="modal-btn" style="background: #27ae60;">Entendido</button>
        `;

        // Cambiamos el borde superior a verde
        alertContent.style.borderTop = "10px solid #2ecc71";
        
        customAlert.style.display = 'flex';
        e.target.reset(); 
    } else if (result.redirect) {
        window.location.href = result.redirect;
    }
} else {
            // ==========================================
            //  ALERTS CON DISEÑO PARA ERRORES
            
            const customAlert = document.getElementById('customAlert');
            const alertContent = customAlert.querySelector('.modal-content');
            
            alertContent.innerHTML = `
                <div class="modal-icon" style="background: #e74c3c;">×</div>
                <h2 style="color: #c0392b;">Error de Acceso</h2>
                <div id="alertMessage">
                    <div style="color: #721c24; background: #f8d7da; padding: 15px; border-radius: 8px; border: 1px solid #f5c6cb; margin-top: 15px;">
                        <i class="ri-error-warning-line" style="font-size: 2rem; display:block; margin-bottom:10px;"></i>
                        <p><strong>DETALLE DEL ERROR:</strong></p>
                        <p>${result.message}</p>
                    </div>
                </div>
                <button onclick="closeAlertAndRedirect()" class="modal-btn" style="background: #e74c3c;">Entendido</button>
            `;
            
            alertContent.style.borderTop = "10px solid #e74c3c";
            customAlert.style.display = 'flex';
        }
    } catch (error) {
        // Alert con diseño para error de conexión
        const customAlert = document.getElementById('customAlert');
        const alertContent = customAlert.querySelector('.modal-content');
        alertContent.innerHTML = `
            <div class="modal-icon" style="background: #95a5a6;">!</div>
            <h2>Servidor no disponible</h2>
            <p>No se pudo conectar con el sistema clínico.</p>
            <button onclick="closeAlertAndRedirect()" class="modal-btn">Cerrar</button>
        `;
        customAlert.style.display = 'flex';
    }
};

    if (loginForm) loginForm.addEventListener('submit', (e) => handleFormSubmit(e, '/login'));
    if (registerForm) registerForm.addEventListener('submit', (e) => handleFormSubmit(e, '/register'));
});
