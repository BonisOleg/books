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
            el: thumb
        });
    });

    if (items.length === 0) return;

    function showItem(index) {
        if (index < 0) index = items.length - 1;
        if (index >= items.length) index = 0;
        currentIndex = index;

        var item = items[index];
        thumbs.forEach(function (t) { t.classList.remove('is-active'); });
        item.el.classList.add('is-active');

        item.el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });

        mainContainer.innerHTML = '';
        if (item.type === 'video') {
            if (item.src.includes('youtube') || item.src.includes('youtu.be')) {
                var videoId = item.src.match(/(?:v=|\/embed\/|youtu\.be\/)([^&?#]+)/);
                if (videoId) {
                    var iframe = document.createElement('iframe');
                    iframe.src = 'https://www.youtube.com/embed/' + encodeURIComponent(videoId[1]) + '?autoplay=1';
                    iframe.style.cssText = 'width:100%;height:100%;border:none;';
                    iframe.setAttribute('allowfullscreen', '');
                    mainContainer.appendChild(iframe);
                }
            } else {
                var video = document.createElement('video');
                video.src = item.src;
                video.controls = true;
                video.autoplay = true;
                video.style.cssText = 'width:100%;height:100%;object-fit:contain;';
                mainContainer.appendChild(video);
            }
        } else {
            var img = document.createElement('img');
            img.src = item.src;
            img.alt = '';
            img.style.cssText = 'width:100%;height:100%;object-fit:contain;';
            mainContainer.appendChild(img);
        }
    }

    thumbs.forEach(function (thumb, i) {
        thumb.addEventListener('click', function () {
            showItem(i);
        });
    });

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            showItem(currentIndex - 1);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            showItem(currentIndex + 1);
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
                if (diff > 0) {
                    showItem(currentIndex + 1);
                } else {
                    showItem(currentIndex - 1);
                }
            }
        }, { passive: true });
    }

    document.addEventListener('keydown', function (e) {
        var tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
        if (e.key === 'ArrowLeft') showItem(currentIndex - 1);
        if (e.key === 'ArrowRight') showItem(currentIndex + 1);
    });
});
