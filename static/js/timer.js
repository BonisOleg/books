document.addEventListener('DOMContentLoaded', function () {
    var timers = document.querySelectorAll('[data-countdown]');

    timers.forEach(function (el) {
        var endTime = parseInt(el.dataset.countdown, 10);
        if (!endTime) return;

        var expiredLabel = el.dataset.expiredLabel || 'Акція завершена';
        var labelDays = el.dataset.labelDays || 'дн';
        var labelHours = el.dataset.labelHours || 'год';
        var labelMinutes = el.dataset.labelMinutes || 'хв';
        var labelSeconds = el.dataset.labelSeconds || 'сек';

        function update() {
            var now = Math.floor(Date.now() / 1000);
            var diff = endTime - now;

            if (diff <= 0) {
                el.innerHTML = '<span style="color:var(--color-text-muted);">' + expiredLabel + '</span>';
                return;
            }

            var days = Math.floor(diff / 86400);
            var hours = Math.floor((diff % 86400) / 3600);
            var minutes = Math.floor((diff % 3600) / 60);
            var seconds = diff % 60;

            el.innerHTML =
                '<div class="timer">' +
                (days > 0 ? '<div class="timer__block"><span class="timer__num">' + days + '</span><span class="timer__label">' + labelDays + '</span></div>' : '') +
                '<div class="timer__block"><span class="timer__num">' + String(hours).padStart(2, '0') + '</span><span class="timer__label">' + labelHours + '</span></div>' +
                '<div class="timer__block"><span class="timer__num">' + String(minutes).padStart(2, '0') + '</span><span class="timer__label">' + labelMinutes + '</span></div>' +
                '<div class="timer__block"><span class="timer__num">' + String(seconds).padStart(2, '0') + '</span><span class="timer__label">' + labelSeconds + '</span></div>' +
                '</div>';

            setTimeout(update, 1000);
        }

        update();
    });
});
