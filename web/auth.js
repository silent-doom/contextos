'use strict';
// Browser credentials go directly to Firebase; only the resulting ID token is
// exchanged with our backend. Tokens are never persisted by this client.
window.contextosIdentity = (() => {
  let config;
  async function configuration() {
    const response = await fetch('/api/auth/config', {credentials:'same-origin',cache:'no-store'});
    if (!response.ok) throw new Error('Sign-in is temporarily unavailable. Please retry.');
    config = await response.json();
    return config;
  }
  async function sessionRequest(path, body) {
    await configuration();
    const response = await fetch(`/api/auth/${path}`, {
      method:'POST',credentials:'same-origin',cache:'no-store',
      headers:{'Content-Type':'application/json','X-ContextOS-Client':'workspace','X-ContextOS-CSRF':config.csrf_token},
      body:JSON.stringify(body)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail==='string' ? result.detail : 'Sign-in could not complete. Please retry.');
    return result;
  }
  async function signIn(email, password) {
    await configuration();
    if (!config.login_ready || config.auth_mode!=='firebase') throw new Error('Sign-in is temporarily unavailable. Please contact your workspace administrator.');
    let response;
    try {
      response = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${encodeURIComponent(config.firebase_api_key)}`, {
        method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({email,password,returnSecureToken:true})
      });
    } catch {
      throw new Error('Could not connect. Check your connection and retry.');
    }
    if (!response.ok) {
      if (response.status===429) throw new Error('Too many sign-in attempts. Wait a moment and retry.');
      throw new Error('Could not sign in. Check your credentials or contact your workspace administrator.');
    }
    const result = await response.json();
    if (typeof result.idToken!=='string' || !result.idToken) throw new Error('Sign-in could not complete. Please retry.');
    return sessionRequest('session',{id_token:result.idToken});
  }
  return {configuration,signIn,signOut:()=>sessionRequest('logout',{})};
})();
