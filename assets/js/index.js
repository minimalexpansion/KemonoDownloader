hljs.highlightAll();

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
}

function hideImageOverlay() {
    overlay.classList.remove('active');
    document.body.style.overflow = 'auto';
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
        backToTopButton.style.display = 'flex';
    } else {
        backToTopButton.style.display = 'none';
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