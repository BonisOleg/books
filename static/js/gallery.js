document.addEventListener('DOMContentLoaded', function () {
    var thumbs = document.querySelectorAll('.product-gallery__thumb');
    var mainContainer = document.getElementById('gallery-main');
    var prevBtn = document.getElementById('gallery-prev');
    var nextBtn = document.getElementById('gallery-next');
    var counterEl = document.getElementById('gallery-counter');
    var playVideoBtn = document.getElementById('gallery-play-video');
    var currentIndex = 0;
    var items = [];
    var firstVideoIndex = -1;

    thumbs.forEach(function (thumb) {
        items.push({
            type: thumb.dataset.type,
            src: thumb.dataset.src,
            srcset: thumb.dataset.srcset || '',
            full: thumb.dataset.full || thumb.dataset.src,
            embed: thumb.dataset.embed || '',
            el: thumb,
        });
    });

    for (var vi = 0; vi < items.length; vi++) {
        if (items[vi].type === 'video') {
            firstVideoIndex = vi;
            break;
        }
    }

    if (items.length === 0) return;

    function parseYoutubeTime(value) {
        if (!value) return 0;
        var raw = String(value).trim().toLowerCase();
        if (/^\d+$/.test(raw)) return parseInt(raw, 10);
        var match = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(raw);
        if (!match || (!match[1] && !match[2] && !match[3])) return 0;
        return (parseInt(match[1] || '0', 10) * 3600)
            + (parseInt(match[2] || '0', 10) * 60)
            + parseInt(match[3] || '0', 10);
    }

    function youtubeEmbedUrl(src) {
        if (!src) return '';
        var raw = String(src).trim();
        if (!/^https?:\/\//i.test(raw)) raw = 'https://' + raw;
        var url;
        try {
            url = new URL(raw);
        } catch (e) {
            return '';
        }
        var host = url.hostname.toLowerCase().replace(/\.$/, '').replace(/^www\./, '');
        if (host !== 'youtube.com' && host !== 'm.youtube.com' && host !== 'youtu.be' && host !== 'youtube-nocookie.com') {
            return '';
        }
        var parts = url.pathname.split('/').filter(Boolean);
        var id = '';
        if (host === 'youtu.be') {
            id = parts[0] || '';
        } else if (parts[0] === 'embed' || parts[0] === 'shorts' || parts[0] === 'live' || parts[0] === 'v') {
            id = parts[1] || '';
        } else {
            id = url.searchParams.get('v') || '';
        }
        if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return '';
        var start = parseYoutubeTime(url.searchParams.get('start') || '');
        if (!start) start = parseYoutubeTime(url.searchParams.get('t') || '');
        var embed = 'https://www.youtube.com/embed/' + id;
        if (start) embed += '?start=' + start;
        return embed;
    }

    function formatCounter(index, total) {
        return (index + 1) + '/' + total;
    }

    function updateCounter(index) {
        if (counterEl) {
            counterEl.textContent = formatCounter(index, items.length);
        }
    }

    function createYoutubeIframe(embedSrc) {
        var iframe = document.createElement('iframe');
        iframe.src = embedSrc + (embedSrc.indexOf('?') === -1 ? '?autoplay=1' : '&autoplay=1');
        iframe.className = 'product-gallery__iframe';
        iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
        iframe.setAttribute('allow', 'autoplay; fullscreen');
        iframe.setAttribute('allowfullscreen', '');
        iframe.title = 'Відео';
        return iframe;
    }

    function createNativeVideo(src) {
        var video = document.createElement('video');
        video.src = src;
        video.controls = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        video.setAttribute('webkit-playsinline', '');
        video.className = 'product-gallery__video';
        return video;
    }

    function showItem(index) {
        if (index < 0) index = items.length - 1;
        if (index >= items.length) index = 0;
        currentIndex = index;

        var item = items[index];
        thumbs.forEach(function (t) { t.classList.remove('is-active'); });
        item.el.classList.add('is-active');
        item.el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });

        mainContainer.innerHTML = '';
        mainContainer.classList.toggle('product-gallery__main--video', item.type === 'video');
        if (playVideoBtn) {
            playVideoBtn.classList.toggle('is-hidden', item.type === 'video');
        }
        updateCounter(index);

        if (item.type === 'video') {
            var embedSrc = item.embed || youtubeEmbedUrl(item.src);
            if (embedSrc) {
                mainContainer.appendChild(createYoutubeIframe(embedSrc));
            } else {
                mainContainer.appendChild(createNativeVideo(item.src));
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
        thumb.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                showItem(i);
            }
        });
    });

    if (prevBtn) prevBtn.addEventListener('click', function () { showItem(currentIndex - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { showItem(currentIndex + 1); });

    if (playVideoBtn) {
        playVideoBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (firstVideoIndex >= 0) showItem(firstVideoIndex);
        });
    }

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

    updateCounter(0);

    var lightbox = null;
    var lightboxImg = null;
    var lightboxMedia = null;
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
            '<div class="lightbox__media"></div>' +
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

        lightboxMedia = lightbox.querySelector('.lightbox__media');
        lightboxImg = document.createElement('img');
        lightboxImg.className = 'lightbox__img';
        lightboxImg.alt = '';
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
        if (items.length === 0) return;
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
        if (lightboxMedia) lightboxMedia.innerHTML = '';
    }

    function navLightbox(delta) {
        lightboxIndex = (lightboxIndex + delta + items.length) % items.length;
        renderLightbox();
    }

    function renderLightbox() {
        var item = items[lightboxIndex];
        lightboxMedia.innerHTML = '';
        lightboxCounter.textContent = formatCounter(lightboxIndex, items.length);

        if (item.type === 'video') {
            var embedSrc = item.embed || youtubeEmbedUrl(item.src);
            if (embedSrc) {
                var iframe = createYoutubeIframe(embedSrc);
                iframe.className = 'lightbox__iframe product-gallery__iframe';
                lightboxMedia.appendChild(iframe);
            } else {
                var video = createNativeVideo(item.src);
                video.className = 'lightbox__video product-gallery__video';
                lightboxMedia.appendChild(video);
            }
        } else {
            lightboxImg.src = item.full || item.src;
            lightboxImg.removeAttribute('srcset');
            lightboxMedia.appendChild(lightboxImg);
        }
    }

    if (mainContainer) {
        mainContainer.addEventListener('click', function () {
            var item = items[currentIndex];
            if (!item || item.type === 'video') return;
            openLightbox(currentIndex);
        });
    }

    document.addEventListener('keydown', function (e) {
        if (!lightbox || !lightbox.classList.contains('is-open')) return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') navLightbox(-1);
        if (e.key === 'ArrowRight') navLightbox(1);
    });
});
