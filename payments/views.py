print("payments.views loaded") # Added for debugging
import razorpay
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from users.models import User, UserProfile
from .models import Payment
import json
from django.contrib.auth.decorators import login_required

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def add_money(request):
    if request.method == "POST":
        amount = int(request.POST.get('amount')) * 100  # Amount in cents
        currency = 'USD'
        try:
            order = razorpay_client.order.create({
                'amount': amount,
                'currency': currency,
                'receipt': f'receipt_add_money_{request.user.id}',
                'payment_capture': '1'
            })
            return render(request, 'payments/payment.html', {
                'order_id': order['id'],
                'amount': amount,
                'currency': currency,
                'key_id': settings.RAZORPAY_KEY_ID,
                'callback_url': request.build_absolute_uri('/payments/payment-success/')
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return render(request, 'payments/add_money.html')

@csrf_exempt
@login_required
def payment_success(request):
    if request.method == "POST":
        try:
            params_dict = {
                'razorpay_order_id': request.POST.get('razorpay_order_id'),
                'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
                'razorpay_signature': request.POST.get('razorpay_signature')
            }
            razorpay_client.utility.verify_payment_signature(params_dict)
            
            # Update user's balance
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            amount = int(razorpay_client.order.fetch(params_dict['razorpay_order_id'])['amount']) / 100
            user_profile.paid_plan_credits += amount
            user_profile.save()

            # Create payment record
            Payment.objects.create(
                user=request.user,
                razorpay_order_id=params_dict['razorpay_order_id'],
                razorpay_payment_id=params_dict['razorpay_payment_id'],
                amount=amount,
                currency='USD',
                is_successful=True
            )
            return redirect('profile')
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@require_POST
@csrf_exempt
def create_razorpay_order(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    amount = 500 # 500 paise = 5 INR (or 5 USD, depending on currency setup)
    currency = 'INR' # Or 'USD'

    try:
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': currency,
            'receipt': f'receipt_itinerary_{request.user.id}_{request.user.free_itineraries_count + 1}',
            'payment_capture': '1' # Auto capture payment
        })
        return JsonResponse({
            'order_id': order['id'],
            'amount': amount,
            'currency': currency,
            'key_id': settings.RAZORPAY_KEY_ID
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@csrf_exempt
def create_prepaid_order(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    # Amount for 5 prepaid itineraries
    amount = 2500 # 2500 paise = 25 INR (or 25 USD)
    currency = 'INR' # Or 'USD'

    try:
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': currency,
            'receipt': f'receipt_prepaid_{request.user.id}_{amount}',
            'payment_capture': '1'
        })
        return JsonResponse({
            'order_id': order['id'],
            'amount': amount,
            'currency': currency,
            'key_id': settings.RAZORPAY_KEY_ID
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    try:
        # Verify webhook signature
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        razorpay_client.utility.verify_payment_signature(params_dict)

        print(f"Payment successful for Order ID: {razorpay_order_id}, Payment ID: {razorpay_payment_id}")

        return HttpResponse(status=200)

    except Exception as e:
        print(f"Razorpay Webhook Error: {e}")
        return HttpResponse(status=400)

# This view will be called by the frontend after successful payment to create the trip
@require_POST
@csrf_exempt
def confirm_paid_itinerary_creation(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    user = request.user

    try:
        data = json.loads(request.body)
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        amount = 500 # Hardcoded for now, should come from order or frontend
        currency = 'INR' # Hardcoded for now

        Payment.objects.create(
            user=user,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            amount=amount / 100, # Convert paise to actual amount
            currency=currency,
            is_successful=True
        )
    except Exception as e:
        print(f"Error creating Payment object: {e}")
        # Continue with trip creation even if payment object creation fails, but log it.

    return JsonResponse({'message': 'Itinerary creation confirmed after payment.'})

@require_POST
@csrf_exempt
def confirm_prepaid_purchase(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    user = request.user

    try:
        data = json.loads(request.body)
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        amount = 2500 # Hardcoded for now
        currency = 'INR' # Hardcoded for now

        Payment.objects.create(
            user=user,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            amount=amount / 100,
            currency=currency,
            is_successful=True
        )

        # Add 5 prepaid itineraries to the user's account
        user.prepaid_itineraries_count += 5
        user.save()

        return JsonResponse({'message': 'Prepaid itineraries purchased successfully.'})
    except Exception as e:
        print(f"Error confirming prepaid purchase: {e}")
        return JsonResponse({'error': 'An error occurred while confirming the purchase.'}, status=400)
