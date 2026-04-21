def process_cod_order(order):
    order.payment_status = 'pending'
    order.save()
