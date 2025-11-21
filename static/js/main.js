document.addEventListener('DOMContentLoaded', () => {
    const logout = document.getElementById("logout");
    const historyBtn = document.getElementById("history");
    const searchbar = document.getElementById("search-input");

    if(searchbar){
        const historyDrop = document.getElementsByClassName("recent-history")[0];
        if(historyDrop){
            searchbar.addEventListener("focus", (e) => {
                historyDrop.style.display = "block";
            })
            
            searchbar.addEventListener("blur", (e) => {
                historyDrop.style.display = "block";
            })

            historyDrop.addEventListener("focus", (e) => {
                historyDrop.style.display = "block";
            })

            historyDrop.addEventListener("blur",(e) => {
                historyDrop.style.display = "none";
            })
            document.querySelectorAll(".history-item").forEach(item => {
            item.addEventListener("click",(e) => {
                searchbar.value = item.textContent;
                historyDrop.style.display = "none";
            })
        });
        }
    }

    if (logout) {
        logout.addEventListener("click", (e) => {
            e.preventDefault();
            fetch("/logout", { method: "POST" })
                .then((res) => res.json())
                .then((data) => {
                    if (data.login === false) {
                        alert("Logged out successfully!");
                        window.location.href = "/"; 
                        // location.reload();
                    }
                })
                .catch((err) => console.error("Logout failed:", err));
        });
    }

    if (historyBtn) {
        historyBtn.addEventListener("click", (e) => {
            e.preventDefault();
            window.location.href = "/history"; 
        });
    }




    // Shared function to handle login and registration on each page
    const handleAuthMod = () => {
        const authMod = document.getElementById('auth-mod');
        if (!authMod) return;
        authMod.style.display = 'none';
        // var authForm = document.getElementById("auth-form");
        const modTitle = document.getElementById('mod-title');
        const modActionBut = document.getElementById('mod-action-btn');
        const modSwitchText = document.getElementById('mod-switch-text');
        const loginBut = document.getElementById('login-but');
        const registerBut = document.getElementById('register-but');
        const closeModBut = document.getElementById('close-modal-btn');
        const authForm = document.getElementById('auth-form');
        const loginFormDiv = document.getElementById('login-form-div');

        const openMod = (isLogin = true) => {
            if (isLogin) {
                modTitle.textContent = 'Login';
                modActionBut.textContent = 'Login';
                loginFormDiv.innerHTML = '<input type="email" placeholder="Email Address" class="form-input" name="email" id="login-email" required><input type="password" placeholder="Password" class="form-input" name="password" id = "login-pwd" required>'
                modSwitchText.innerHTML = `Create An Account Today: <a href="#" id="mod-switch-link" class="link">Register</a>`;
            } else {
                modTitle.textContent = 'Registration';
                modActionBut.textContent = 'Create Account';
                loginFormDiv.innerHTML = '<input type="text" placeholder="Name" class="form-input" name="name" id="reg-name" required><input type="date" placeholder="Date Of Birth" class="form-input" name="dob" id = "reg-dob" required>' + loginFormDiv.innerHTML;
                modSwitchText.innerHTML = `Already have an account? <a href="#" id="mod-switch-link" class="link">Login</a>`;
            }
            authMod.style.display = 'flex';
            const link = document.getElementById('mod-switch-link');
            if (link) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    openMod(modTitle.textContent === 'Registration');
                });
            }
        };

        const closeMod = () => {
            authMod.style.display = 'none';
        };

        if (loginBut) loginBut.onclick = () => openMod(true);
        if (registerBut) registerBut.onclick = () => openMod(false);
        if (closeModBut) closeModBut.onclick = closeMod;
        authMod.addEventListener('click', (e) => { if (e.target === authMod) closeMod(); });
        if (authForm) {
            authForm.addEventListener('submit', (e) => {
                e.preventDefault();
                if (modTitle.textContent === 'Registration') {
                    const email = document.getElementById("login-email").value;
                    const pwd = document.getElementById("login-pwd").value;
                    const name = document.getElementById("reg-name").value;
                    const dob = document.getElementById("reg-dob").value;
                    fetch('/register', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ "email": email, "pwd": pwd, "name": name, "dob": dob })
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data["registration"] == 0) {
                                alert(`${modTitle.textContent} successful`);
                                openMod(true);
                            }
                        });
                }
                else {
                    var email = document.getElementById("login-email").value;
                    var pwd = document.getElementById("login-pwd").value;
                    fetch('/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ "email": email, "pwd": pwd })
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data["login"] == false) {
                                alert(`${modTitle.textContent} credentials not found`);
                            }
                            else {
                                alert(`${modTitle.textContent} successful`);
                                closeMod();
                                location.reload();
                            }
                        });
                }
            });
        }
    };

    handleAuthMod();
});


function toggleSnippet(button) {
    const snippet = button.parentElement.querySelector('.snippet');
    if (snippet.classList.contains('hidden')) {
        snippet.classList.remove('hidden');
        button.textContent = "Hide Summary";
    } else {
        snippet.classList.add('hidden');
        button.textContent = "Show Summary";
    }
}