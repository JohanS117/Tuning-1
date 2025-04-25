document.querySelector('.boton-sesion button').addEventListener('mouseenter', function() {
    anime({
    targets: this,
    scale: [
        { value: 1.1, easing: 'easeOutSine', duration: 400 },
        { value: 1, easing: 'easeInOutQuad', duration: 200 }
    ],
    backgroundColor: '#2563eb',
    boxShadow: [
        { value: '0 6px 15px rgba(0, 0, 0, 0.3)', duration: 400 }
    ],
    easing: 'easeOutQuad',
    duration: 600,
    loop: true,
    delay: 3500
    });
});

document.querySelector('.boton-registro button').addEventListener('mouseenter', function() {
    anime({
    targets: this,
    scale: [
        { value: 1.1, easing: 'easeOutSine', duration: 400 },
        { value: 1, easing: 'easeInOutQuad', duration: 200 }
    ],
    backgroundColor: '#059669',
    boxShadow: [
        { value: '0 6px 15px rgba(0, 0, 0, 0.3)', duration: 400 }
    ],
    easing: 'easeOutQuad',
    duration: 600,
    loop: true,
    delay: 3500
    });
});

document.querySelector('.boton-sesion button').addEventListener('click', function() {
    anime({
    targets: this,
    scale: [
        { value: 0.95, easing: 'easeOutQuad', duration: 200 },
        { value: 1, easing: 'easeInOutQuad', duration: 300 }
    ],
    easing: 'easeOutQuad'
    });
});

document.querySelector('.boton-registro button').addEventListener('click', function() {
    anime({
    targets: this,
    scale: [
        { value: 0.95, easing: 'easeOutQuad', duration: 200 },
        { value: 1, easing: 'easeInOutQuad', duration: 300 }
    ],
    easing: 'easeOutQuad'
    });
});