from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Cart, CartItem
from store.models import Product
from django.core.exceptions import ObjectDoesNotExist

# Create your views here.

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_to_cart(request, product_id):
    product = Product.objects.get(id=product_id) #get the product by id
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request)) #get the cart by id
    except Cart.DoesNotExist:
        cart = Cart.objects.create(cart_id=_cart_id(request)) #create a new cart if it does not exist
    cart.save()
    
    try:
        cart_item = CartItem.objects.get(product=product, cart=cart) #get the cart item by product and cart
        cart_item.quantity += 1 #increment the quantity if it exists
        cart_item.save()
    except CartItem.DoesNotExist:
        cart_item = CartItem.objects.create(product=product, quantity=1, cart=cart)
        cart_item.save()
    
    return redirect('cart')

def remove_cart(request, product_id):
    cart = Cart.objects.get(cart_id=_cart_id(request)) 
    product = get_object_or_404(Product, id=product_id) 
    cart_item = CartItem.objects.get(product=product, cart=cart)
    if cart_item.quantity > 1:
        cart_item.quantity -= 1 
        cart_item.save()
    else:
        cart_item.delete() #delete the cart item if the quantity is 1
    
    return redirect('cart')

def remove_cart_item(request, product_id):
    cart = Cart.objects.get(cart_id=_cart_id(request)) 
    product = get_object_or_404(Product, id=product_id) 
    cart_item = CartItem.objects.get(product=product, cart=cart)
    cart_item.delete()
    
    return redirect('cart')

def cart(request, total=0, quantity=0, cart_items=None):
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request)) 
        cart_items = CartItem.objects.filter(cart=cart, is_active=True) 
        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity) #calculate the total price
            quantity += cart_item.quantity #calculate the total quantity
            
        tax = (2 * total) / 100
        grand_total = total + tax 
            
    except ObjectDoesNotExist:
        pass
    
    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/cart.html', context) 
