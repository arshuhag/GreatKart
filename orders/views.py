from django.shortcuts import render, redirect
from django.http import JsonResponse
from carts.models import CartItem
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
from store.models import Product
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

import datetime, json, requests


def payments(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)  # Parsing the incoming JSON body

            # Extract orderID and other necessary data
            order_id = body.get('orderID')  # Extracting orderID from the request body
            amount = body.get('amount')
            currency = body.get('currency')

            if not order_id or not amount or not currency:
                return JsonResponse({'error': 'Missing required fields (orderID, amount, currency)'}, status=400)

            # Get order from the database
            order = Order.objects.get(order_number=order_id)

            sslcz = {
                'store_id': settings.SSLCOMMERZ_STORE_ID,
                'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
                'total_amount': str(order.order_total),
                'currency': "BDT",
                'tran_id': order.order_number,
                'success_url': request.build_absolute_uri(reverse('ssl_success')),
                'fail_url': request.build_absolute_uri(reverse('ssl_fail')),
                'cancel_url': request.build_absolute_uri(reverse('ssl_cancel')),
                'emi_option': 0,
                'cus_name': f"{order.first_name} {order.last_name}",
                'cus_email': order.email,
                'cus_add1': order.address_line_1,
                'cus_city': order.city,
                'cus_state': order.state,
                'cus_postcode': order.zip_code,
                'cus_country': order.country,
                'cus_phone': order.phone,
                'shipping_method': "NO",
                'product_name': "GreatKart Products",
                'product_category': "Ecommerce",
                'product_profile': "general",
            }

            response = requests.post("https://sandbox.sslcommerz.com/gwprocess/v4/api.php", data=sslcz)
            res_data = response.json()

            if res_data.get('status') == 'SUCCESS':
                return JsonResponse({'payment_url': res_data['GatewayPageURL']})
            else:
                return JsonResponse({'error': 'Payment initiation failed'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)

def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    if cart_items.count() <= 0:
        return redirect('store')

    # Check stock before proceeding
    for cart_item in cart_items:
        if cart_item.quantity > cart_item.product.stock:
            return JsonResponse({
                'error': f'Only {cart_item.product.stock} items available for {cart_item.product.product_name}'
            }, status=400)

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.zip_code = form.cleaned_data['zip_code']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            current_date = datetime.date.today().strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)

            context = {
                'order': order,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total,
            }
            return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')


@csrf_exempt
def ssl_success(request):
    try:
        # Log the incoming request data
        print("SSL Success Callback Data:")
        print(f"POST data: {request.POST}")
        print(f"GET data: {request.GET}")
        print(f"Body data: {request.body}")

        # Try to get transaction ID from different possible sources
        tran_id = (
            request.POST.get('tran_id') or  # First try POST
            request.GET.get('tran_id') or   # Then try GET
            request.POST.get('order_number') or  # Try alternative field names
            request.GET.get('order_number')
        )
        
        if not tran_id:
            print("No transaction ID found in request")
            return JsonResponse({'error': 'Missing transaction data in the callback'}, status=400)

        print(f"Looking for order with transaction ID: {tran_id}")
        
        # First try to find the order without checking is_ordered
        try:
            order = Order.objects.get(order_number=tran_id)
            print(f"Found order: {order}")
            
            # If order is already processed, return success
            if order.is_ordered:
                print("Order already processed")
                return redirect(reverse('order_complete') + f'?order_number={order.order_number}&payment_id={tran_id}')
                
        except Order.DoesNotExist:
            print(f"No order found with number {tran_id}")
            # Let's check if there are any orders with similar numbers
            similar_orders = Order.objects.filter(order_number__startswith=tran_id[:8])
            if similar_orders.exists():
                print(f"Found similar orders: {list(similar_orders.values_list('order_number', flat=True))}")
            return JsonResponse({'error': f'Order not found with number {tran_id}'}, status=400)

        # Create a new payment record using the order's user
        payment = Payment(
            user=order.user,
            payment_id=tran_id,
            payment_method="SSLCommerz",
            amount_paid=order.order_total,
            status="SUCCESS",
        )
        payment.save()

        # Update order details
        order.payment = payment
        order.is_ordered = True
        order.save()

        # Process the cart items and create the order products
        cart_items = CartItem.objects.filter(user=order.user)
        for item in cart_items:
            orderproduct = OrderProduct(
                order_id=order.id,
                payment=payment,
                user_id=order.user.id,
                product_id=item.product_id,
                quantity=item.quantity,
                product_price=item.product.price,
                ordered=True,
            )
            orderproduct.save()

            # Handle variations if any
            product_variation = item.variations.all()
            orderproduct.variations.set(product_variation)
            orderproduct.save()

            # Reduce stock of the purchased products
            product = Product.objects.get(id=item.product_id)
            product.stock -= item.quantity
            product.save()

        # Clear the user's cart after order placement
        CartItem.objects.filter(user=order.user).delete()

        # Send the confirmation email
        mail_subject = 'Thank you for your order!'
        message = render_to_string('orders/order_recieved_email.html', {
            'user': order.user,
            'order': order,
        })
        to_email = order.user.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.send()

        # Redirect to order complete page
        return redirect(reverse('order_complete') + f'?order_number={order.order_number}&payment_id={payment.payment_id}')

    except Exception as e:
        print(f"Error in ssl_success: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)



@csrf_exempt
def ssl_fail(request):
    return render(request, 'orders/ssl_fail.html')


@csrf_exempt
def ssl_cancel(request):
    return render(request, 'orders/ssl_cancel.html')


def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)
        subtotal = sum(item.product_price * item.quantity for item in ordered_products)
        payment = Payment.objects.get(payment_id=transID)

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')
