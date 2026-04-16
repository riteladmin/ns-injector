(function() {
    function addTraceButton() {
        var nav = document.getElementById('nav-buttons');
        if (!nav) {
            console.log('Call Tracer: nav-buttons not found');
            return;
        }

        if (document.getElementById('nav-calltracer')) return;

        var li = document.createElement('li');
        li.id = 'nav-calltracer';

        var a = document.createElement('a');
        a.href = 'https://trace.cloudworxcx.com';
        a.target = '_blank';
        a.className = 'nav-link';
        a.id = 'LinkCallTracer';

        a.innerHTML = '<div class="nav-button btn"></div>' +
            '<div class="nav-bg-image" style="background-image:url(\'data:image/svg+xml,' +
            encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none"><path d="M18 44V20l8 8 6-10 6 10 8-8v24" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="46" cy="16" r="5" stroke="#4FC3F7" stroke-width="2"/><path d="M46 11v-2M46 23v-2M51 16h2M41 16h-2" stroke="#4FC3F7" stroke-width="1.5" stroke-linecap="round"/></svg>') +
            '\')"></div>' +
            '<span class="nav-text">Call Tracer</span>' +
            '<div class="nav-arrow"></div>';

        li.appendChild(a);
        nav.appendChild(li);
        console.log('Call Tracer: Menu button added to NS portal');
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(addTraceButton, 300);
    } else {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(addTraceButton, 300);
        });
    }
})();
