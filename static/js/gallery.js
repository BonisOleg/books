document.addEventListener('DOMContentLoaded', function () {
    var thumbs = document.querySelectorAll('.product-gallery__thumb');
    var mainContainer = document.getElementById('gallery-main');
    var prevBtn = document.getElementById('gallery-prev');
    var nextBtn = document.getElementById('gallery-next');
    var currentIndex = 0;
    var items = [];

    thumbs.forEach(function (thumb) {
        items.push({
            type: thumb.dataset.type,
            src: thumb.dataset.src,
            srcset: thumb.dataset.srcset || '',
            full: thumb.dataset.full || thumb.dataset.src,
            el: thumb,
        });
    });

    if (items.length === 0) return;

    function isYoutube(src) {
        return src.indexOf('youtube') !== -1 || src.indexOf('youtu.be') !== -1;
    }

    function youtubeEmbed(src) {
        var match = src.match(/(?:v=|\/embed\/|youtu\.be\/)([^&?#]+)/);
        return match ? match[1] : null;
    }

    function showItem(index) {
        if (index < 0) index = items.length - 1;
        if (index >= items.length) index = 0;
        currentIndex = index;

        var item = items[index];
        thumbs.forEach(function (t) { t.classList.remove('is-active'); });
        item.el.classList.add('is-active');
        item.el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });

        mainContainer.innerHTML = '';
        mainContainer.classList.toggle('product-gallery__main--video', item.type === 'video');

        if (item.type === 'video') {
            if (isYoutube(item.src)) {
                var videoId = youtubeEmbed(item.src);
                if (videoId) {
                    var iframe = document.createElement('iframe');
                    iframe.src = 'https://www.youtube.com/embed/' + encodeURIComponent(videoId) + '?autoplay=1';
                    iframe.className = 'product-gallery__iframe';
                    iframe.setAttribute('allowfullscreen', '');
                    mainContainer.appendChild(iframe);
                }
            } else {
                var video = document.createElement('video');
                video.src = item.src;
                video.controls = true;
                video.autoplay = true;
                video.className = 'product-gallery__video';
                mainContainer.appendChild(video);
            }
        } else {
            var img = document.createElement('img');
            img.src = item.src;
            if (item.srcset) {
                img.srcset = item.srcset;
                img.sizes = '(max-width: 767px) 100vw, 640px';
            }
            var thumbImg = item.el.querySelector('img');
            img.alt = thumbImg ? (thumbImg.getAttribute('alt') || '') : '';
            img.id = 'gallery-current';
            mainContainer.appendChild(img);
        }
    }

    thumbs.forEach(function (thumb, i) {
        thumb.addEventListener('click', function () {
            showItem(i);
        });
    });

    if (prevBtn) prevBtn.addEventListener('click', function () { showItem(currentIndex - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { showItem(currentIndex + 1); });

    var touchStartX = 0;
    var touchEndX = 0;
    if (mainContainer) {
        mainContainer.addEventListener('touchstart', function (e) {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });
        mainContainer.addEventListener('touchend', function (e) {
            touchEndX = e.changedTouches[0].screenX;
            var diff = touchStartX - touchEndX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) showItem(currentIndex + 1);
                else showItem(currentIndex - 1);
            }
        }, { passive: true });
    }

    document.addEventListener('keydown', function (e) {
        var tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
        if (lightbox && lightbox.classList.contains('is-open')) return;
        if (e.key === 'ArrowLeft') showItem(currentIndex - 1);
        if (e.key === 'ArrowRight') showItem(currentIndex + 1);
    });

    var imageItems = items.filter(function (i) { return i.type !== 'video'; });
    var lightbox = null;
    var lightboxImg = null;
    var lightboxCounter = null;
    var lightboxIndex = 0;

    function buildLightbox() {
        var labelClose = mainContainer ? (mainContainer.dataset.labelClose || '×') : '×';
        var labelPrev = mainContainer ? (mainContainer.dataset.labelPrev || '‹') : '‹';
        var labelNext = mainContainer ? (mainContainer.dataset.labelNext || '›') : '›';

        lightbox = document.createElement('div');
        lightbox.className = 'lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.innerHTML =
            '<div class="lightbox__stage">' +
            '<img class="lightbox__img" alt="">' +
            '<button type="button" class="lightbox__close" aria-label="' + labelClose + '">×</button>' +
            '<button type="button" class="lightbox__nav lightbox__nav--prev" aria-label="' + labelPrev + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>' +
            '</button>' +
            '<button type="button" class="lightbox__nav lightbox__nav--next" aria-label="' + labelNext + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 6 15 12 9 18"/></svg>' +
            '</button>' +
            '<div class="lightbox__counter"></div>' +
            '</div>';
        document.body.appendChild(lightbox);

        lightboxImg = lightbox.querySelector('.lightbox__img');
        lightboxCounter = lightbox.querySelector('.lightbox__counter');

        lightbox.querySelector('.lightbox__close').addEventListener('click', closeLightbox);
        lightbox.querySelector('.lightbox__nav--prev').addEventListener('click', function () {
            navLightbox(-1);
        });
        lightbox.querySelector('.lightbox__nav--next').addEventListener('click', function () {
            navLightbox(1);
        });
        lightbox.addEventListener('click', function (e) {
            if (e.target === lightbox || e.target.classList.contains('lightbox__stage')) {
                closeLightbox();
            }
        });
    }

    function openLightbox(index) {
        if (imageItems.length === 0) return;
        if (!lightbox) buildLightbox();
        lightboxIndex = index;
        renderLightbox();
        lightbox.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        if (!lightbox) return;
        lightbox.classList.remove('is-open');
        document.body.style.overflow = '';
    }

    function navLightbox(delta) {
        lightboxIndex = (lightboxIndex + delta + imageItems.length) % imageItems.length;
        renderLightbox();
    }

    function renderLightbox() {
        var item = imageItems[lightboxIndex];
        lightboxImg.src = item.full || item.src;
        lightboxImg.removeAttribute('srcset');
        lightboxCounter.textContent = (lightboxIndex + 1) + ' / ' + imageItems.length;
    }

    if (mainContainer) {
        mainContainer.addEventListener('click', function () {
            var item = items[currentIndex];
            if (!item || item.type === 'video') return;
            var imgIndex = imageItems.findIndex(function (i) { return i.src === item.src; });
            if (imgIndex < 0) imgIndex = 0;
            openLightbox(imgIndex);
        });
    }

    document.addEventListener('keydown', function (e) {
        if (!lightbox || !lightbox.classList.contains('is-open')) return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') navLightbox(-1);
        if (e.key === 'ArrowRight') navLightbox(1);
    });
});
