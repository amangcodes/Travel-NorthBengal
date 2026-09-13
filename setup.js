// setup.js

const state = {
    isConfigured: false,
    dbPopulated: false
};

const elements = {
    steps: {
        env: document.getElementById('step-env'),
        migrate: document.getElementById('step-migrate'),
        success: document.getElementById('step-success')
    },
    inputs: {
        supabase_url: document.getElementById('supabase_url'),
        supabase_key: document.getElementById('supabase_key'),
        groq_key: document.getElementById('groq_key')
    },
    btns: {
        saveEnv: document.getElementById('btnSaveEnv'),
        migrate: document.getElementById('btnMigrate')
    },
    progress: {
        container: document.getElementById('progressContainer'),
        bar: document.getElementById('progressBar')
    },
    output: document.getElementById('outputBox'),
    statusContainer: document.getElementById('envStatusContainer')
};

async function checkStatus() {
    try {
        const res = await fetch('/api/setup/status');
        const data = await res.json();
        
        state.isConfigured = data.supabase_configured;
        state.dbPopulated = data.db_populated;
        
        if (data.supabase_url) elements.inputs.supabase_url.value = data.supabase_url;
        
        updateStatusUI(data);
        
        // If configured but not populated, go to migrate step
        if (state.isConfigured && !state.dbPopulated) {
            showStep('migrate');
        } else if (state.isConfigured && state.dbPopulated) {
           // If everything is done, maybe show success or stay on migrate for re-sync
           // For initial setup, we show success
        }
    } catch (err) {
        console.error('Failed to check status:', err);
    }
}

function updateStatusUI(data) {
    elements.statusContainer.innerHTML = `
        <div class="status-pill ${data.supabase_configured ? 'online' : 'offline'}">
            ${data.supabase_configured ? 'Supabase: Connected' : 'Supabase: Pending'}
        </div>
        <div class="status-pill ${data.groq_configured ? 'online' : 'offline'}" style="margin-left: 8px;">
            ${data.groq_configured ? 'AI Brain: ready' : 'AI Brain: Pending'}
        </div>
    `;
}

function showStep(stepName) {
    Object.values(elements.steps).forEach(s => s.classList.remove('is-active'));
    elements.steps[stepName].classList.add('is-active');
}

elements.btns.saveEnv.addEventListener('click', async () => {
    const payload = {
        supabase_url: elements.inputs.supabase_url.value.trim(),
        supabase_key: elements.inputs.supabase_key.value.trim(),
        groq_key: elements.inputs.groq_key.value.trim()
    };
    
    if (!payload.supabase_url || !payload.supabase_key) {
        alert('Please enter at least the Supabase credentials.');
        return;
    }
    
    elements.btns.saveEnv.classList.add('is-loading');
    elements.btns.saveEnv.textContent = 'Saving...';
    
    try {
        const res = await fetch('/api/setup/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            await checkStatus();
            showStep('migrate');
        } else {
            const err = await res.json();
            alert('Error: ' + err.message);
        }
    } catch (err) {
        alert('Failed to connect to backend.');
    } finally {
        elements.btns.saveEnv.classList.remove('is-loading');
        elements.btns.saveEnv.innerHTML = '<span>Save Configuration</span><span class="icon">→</span>';
    }
});

elements.btns.migrate.addEventListener('click', async () => {
    elements.btns.migrate.classList.add('is-loading');
    elements.btns.migrate.textContent = 'Migrating Data...';
    elements.progress.container.style.display = 'block';
    elements.output.style.display = 'block';
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += (95 - progress) * 0.1;
        elements.progress.bar.style.width = progress + '%';
    }, 500);
    
    try {
        const res = await fetch('/api/setup/migrate', { method: 'POST' });
        const data = await res.json();
        
        clearInterval(interval);
        elements.progress.bar.style.width = '100%';
        elements.output.textContent = data.message + '\n\n' + (data.output || '');
        
        if (res.ok) {
            setTimeout(() => showStep('success'), 1500);
        } else {
            alert('Migration failed: ' + data.message);
        }
    } catch (err) {
        clearInterval(interval);
        alert('Critical error during migration.');
    } finally {
        elements.btns.migrate.classList.remove('is-loading');
        elements.btns.migrate.innerHTML = '<span>Start Cloud Sync</span><span class="icon">☁️</span>';
    }
});

// Init
document.addEventListener('DOMContentLoaded', checkStatus);
