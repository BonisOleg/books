document.addEventListener('DOMContentLoaded', function () {
    var timers = document.querySelectorAll('[data-countdown]');

    timers.forEach(function (el) {
        var endTime = parseInt(el.dataset.countdown, 10);
        if (!endTime) return;

        function update() {
            var now = Math.floor(Date.now() / 1000);
            var diff = endTime - now;

            if (diff <= 0) {
                el.innerHTML = '<span style="color:var(--color-text-muted);">Акція завершена</span>';
                return;
            }

            var days = Math.floor(diff / 86400);
            var hours = Math.floor((diff % 86400) / 3600);
            var minutes = Math.floor((diff % 3600) / 60);
            var seconds = diff % 60;

            el.innerHTML =
                '<div class="timer">' +
                (days > 0 ? '<div class="timer__block"><span class="timer__num">' + days + '</span><span class="timer__label">дн</span></div>' : '') +
                '<div class="timer__block"><span class="timer__num">' + String(hours).padStart(2, '0') + '</span><span class="timer__label">год</span></div>' +
                '<div class="timer__block"><span class="timer__num">' + String(minutes).padStart(2, '0') + '</span><span class="timer__label">хв</span></div>' +
                '<div class="timer__block"><span class="timer__num">' + String(seconds).padStart(2, '0') + '</span><span class="timer__label">сек</span></div>' +
                '</div>';

            setTimeout(update, 1000);
        }

        update();
    });
});
