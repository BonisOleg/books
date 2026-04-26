document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-modal-close]');
    if (!trigger) {
        return;
    }

    var modal = trigger.closest('.modal');
    if (modal) {
        modal.remove();
    }
});
