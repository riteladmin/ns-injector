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
            encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none"><g transform="translate(4,4) scale(2.333)"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1H6.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" fill="#fff"/><circle cx="16" cy="6" r="3.5" fill="none" stroke="#fff" stroke-width="1"/><line x1="18.5" y1="8.5" x2="21.5" y2="11.5" stroke="#fff" stroke-width="1" stroke-linecap="round"/></g></svg>') +
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
