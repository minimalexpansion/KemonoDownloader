hljs.highlightAll();
    
    AOS.init({
        duration: 800,
        easing: 'ease-in-out',
        once: true,
        mirror: false
    });

    let currentZoomLevel = 1;
    const overlay = document.getElementById('imageOverlay');
    const overlayImage = document.getElementById('overlayImage');
    const closeBtn = document.getElementById('closeOverlayBtn');

    function showImageOverlay(src) {
        overlayImage.src = src;
        overlay.classList.add('active');
        currentZoomLevel = 1;
        overlayImage.style.transform = `scale(${currentZoomLevel})`;
        document.body.style.overflow = 'hidden';
        
        setTimeout(() => {
            overlayImage.style.opacity = '1';
        }, 100);
    }

    function hideImageOverlay() {
        overlayImage.style.opacity = '0';
        setTimeout(() => {
            overlay.classList.remove('active');
            document.body.style.overflow = 'auto';
        }, 300);
    }

    closeBtn.addEventListener('click', (event) => {
        event.preventDefault();
        hideImageOverlay();
    });

    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            hideImageOverlay();
        }
    });

    overlayImage.addEventListener('wheel', (event) => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? -0.1 : 0.1; 
        currentZoomLevel = Math.min(Math.max(currentZoomLevel + delta, 0.5), 2);
        overlayImage.style.transform = `scale(${currentZoomLevel})`;
    });

    const backToTopButton = document.getElementById('back-to-top');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            backToTopButton.classList.add('visible');
        } else {
            backToTopButton.classList.remove('visible');
        }
    });

    backToTopButton.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    window.addEventListener('scroll', function() {
        const scrollPosition = window.scrollY;
        const header = document.querySelector('header');
        const headerContent = document.querySelector('header .app-image');
        
        if (scrollPosition < 600) {
            headerContent.style.transform = `translateY(${scrollPosition * 0.2}px)`;
            header.style.backgroundPosition = `center ${scrollPosition * 0.5}px`;
        }
    });

    document.querySelectorAll('.btn-custom').forEach(button => {
        button.addEventListener('mouseover', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        button.addEventListener('mouseout', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const angleX = (y - centerY) / 20;
            const angleY = (centerX - x) / 20;
            
            this.style.transform = `perspective(1000px) rotateX(${angleX}deg) rotateY(${angleY}deg) translateY(-5px)`;
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateY(0)';
        });
    });