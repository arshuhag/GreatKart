from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Cart, CartItem
from store.models import Product, Variation
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required

# Create your views here.

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_to_cart(request, product_id):
    current_user = request.user
    product = Product.objects.get(id=product_id) #get the product by id
    
    # Check if product is in stock
    if product.stock <= 0:
        return JsonResponse({'error': 'This product is out of stock'}, status=400)
    
    #if the user is authenticated, get the cart items for the user
    if current_user.is_authenticated:
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
        
        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item = CartItem.objects.filter(product=product, user=current_user)
            ex_var_list = []
            id = []
            for item in cart_item:
                exists_variation = item.variations.all() #get the variations of the cart item
                ex_var_list.append(list(exists_variation)) #append the variations to the list
                id.append(item.id) #append the id of the cart item to the list
            
            if product_variation in ex_var_list:
                index = ex_var_list.index(product_variation) #get the index of the product variation
                item_id = id[index] #get the id of the cart item
                item = CartItem.objects.get(product=product, id=item_id) #get the cart item by id
                
                # Check if adding one more would exceed stock
                if item.quantity + 1 > product.stock:
                    return JsonResponse({'error': f'Only {product.stock} items available in stock'}, status=400)
                    
                item.quantity += 1 #increment the quantity if the product variation exists
                item.save()
            else:
                # Check if product is in stock before creating new cart item
                if product.stock < 1:
                    return JsonResponse({'error': 'This product is out of stock'}, status=400)
                    
                item = CartItem.objects.create(product=product, quantity=1, user=current_user) 
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation)
                item.save()
        else:
            # Check if product is in stock before creating new cart item
            if product.stock < 1:
                return JsonResponse({'error': 'This product is out of stock'}, status=400)
                
            cart_item = CartItem.objects.create(product=product, quantity=1, user=current_user)
            if len(product_variation) > 0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('cart')
    #if the user is not authenticated, get the cart items for the guest user
    else:
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
                index = ex_var_list.index(product_variation) #get the index of the product variation
                item_id = id[index] #get the id of the cart item
                item = CartItem.objects.get(product=product, id=item_id) #get the cart item by id
                
                # Check if adding one more would exceed stock
                if item.quantity + 1 > product.stock:
                    return JsonResponse({'error': f'Only {product.stock} items available in stock'}, status=400)
                    
                item.quantity += 1 #increment the quantity if the product variation exists
                item.save()
            else:
                # Check if product is in stock before creating new cart item
                if product.stock < 1:
                    return JsonResponse({'error': 'This product is out of stock'}, status=400)
                    
                item = CartItem.objects.create(product=product, quantity=1, cart=cart) 
                if len(product_variation) > 0:
                    item.variations.clear()
                    item.variations.add(*product_variation)
                item.save()
        else:
            # Check if product is in stock before creating new cart item
            if product.stock < 1:
                return JsonResponse({'error': 'This product is out of stock'}, status=400)
                
            cart_item = CartItem.objects.create(product=product, quantity=1, cart=cart)
            if len(product_variation) > 0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('cart')

def remove_cart(request, product_id, cart_item_id):
    
    product = get_object_or_404(Product, id=product_id) 
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request)) 
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
     
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
    cart_item.delete()
    
    return redirect('cart')

def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
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

@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
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
    return render(request, 'store/checkout.html', context)
