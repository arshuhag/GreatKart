from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Cart, CartItem
from store.models import Product, Variation
from django.core.exceptions import ObjectDoesNotExist

# Create your views here.

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_to_cart(request, product_id):
    product = Product.objects.get(id=product_id) #get the product by id
    product_variation = []
    if request.method == 'POST':
        for item in request.POST:
            key = item
            value = request.POST[key]
            try:
                variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                product_variation.append(variation) #append the product variation to the list
            except:
                pass
    
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request)) #get the cart by id
    except Cart.DoesNotExist:
        cart = Cart.objects.create(cart_id=_cart_id(request)) #create a new cart if it does not exist
    cart.save()
    
    is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
    if is_cart_item_exists:
        cart_item = CartItem.objects.filter(product=product, cart=cart)
        ex_var_list = []
        id = []
        for item in cart_item:
            exists_variation = item.variations.all() #get the variations of the cart item
            ex_var_list.append(list(exists_variation)) #append the variations to the list
            id.append(item.id) #append the id of the cart item to the list
        
        if product_variation in ex_var_list:
            item = CartItem.objects.get(product=product, cart=cart, id=id[ex_var_list.index(product_variation)])
            item.quantity += 1 #increment the quantity if the product variation exists
            item.save()
        else:
            item = CartItem.objects.create(product=product, quantity=1, cart=cart) 
            if len(product_variation) > 0:
                item.variations.clear()
                item.variations.add(*product_variation)
            item.save()
    else:
        cart_item = CartItem.objects.create(product=product, quantity=1, cart=cart)
        if len(product_variation) > 0:
            cart_item.variations.clear()
            cart_item.variations.add(*product_variation)
        cart_item.save()
    
    return redirect('cart')

def remove_cart(request, product_id, cart_item_id):
    cart = Cart.objects.get(cart_id=_cart_id(request)) 
    product = get_object_or_404(Product, id=product_id) 
    try:
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1 
            cart_item.save()
        else:
            cart_item.delete() #delete the cart item if the quantity is 1
    except:
        pass
    
    return redirect('cart')

def remove_cart_item(request, product_id, cart_item_id):
    cart = Cart.objects.get(cart_id=_cart_id(request)) 
    product = get_object_or_404(Product, id=product_id) 
    cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
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
