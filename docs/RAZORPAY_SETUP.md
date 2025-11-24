# Razorpay Payment Integration - Installation & Setup

## Quick Start

### 1. Install Razorpay SDK

```bash
pip install razorpay
# or
uv pip install razorpay
```

### 2. Set Environment Variables

Create `.env` file or add to your environment:

```bash
# Razorpay Credentials (Get from https://dashboard.razorpay.com)
RAZORPAY_KEY_ID=rzp_test_xxxxx          # Test key
RAZORPAY_KEY_SECRET=xxxxx                # Secret key  
RAZORPAY_WEBHOOK_SECRET=xxxxx            # Webhook secret

# Environment
RAZORPAY_ENVIRONMENT=sandbox             # sandbox or production

# Limits
PAYMENT_CURRENCY=INR
PAYMENT_MIN_AMOUNT=5
PAYMENT_MAX_AMOUNT=10000
```

### 3. Configure Webhook

1. Go to https://dashboard.razorpay.com/app/webhooks
2. Add webhook URL: `https://yourdomain.com/api/payments/webhooks`
3. Select events:
   - `payment.captured`
   - `payment.failed`
   - `order.paid`
4. Copy webhook secret to `RAZORPAY_WEBHOOK_SECRET`

### 4. Test Integration

```bash
# Test with sandbox credentials
python -c "from second_brain_database.services.razorpay_service import razorpay_service; print('✓ Razorpay service initialized')"
```

## API Endpoints

### Create Payment Order
```http
POST /api/payments/orders
Authorization: Bearer {jwt_token}

{
  "amount_inr": 100,
  "purpose": "sbd_token_purchase"
}
```

### Verify Payment
```http
POST /api/payments/verify

{
  "order_id": "order_xxxxx",
  "payment_id": "pay_xxxxx",
  "signature": "xxxxx"
}
```

### Get Transaction History
```http
GET /api/payments/history
```

## Testing

### Sandbox Test Cards

**Success:**
- Card: `4111 1111 1111 1111`
- CVV: Any 3 digits
- Expiry: Any future date

**Failure:**
- Card: `4000 0000 0000 0002`

### Test UPI IDs
- Success: `success@razorpay`
- Failure: `failure@razorpay`

## Production Checklist

- [ ] Get production Razorpay credentials
- [ ] Update `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`
- [ ] Set `RAZORPAY_ENVIRONMENT=production`
- [ ] Configure production webhook URL
- [ ] Test with small amount (₹10)
- [ ] Monitor first transactions
- [ ] Set up alerts for failed payments

## Documentation

See [SHOP_PRICING_AND_PAYMENTS.md](./SHOP_PRICING_AND_PAYMENTS.md) for complete documentation.
