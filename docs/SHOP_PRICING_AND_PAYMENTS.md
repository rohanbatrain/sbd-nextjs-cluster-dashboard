# Shop Pricing & Payment Integration Documentation

## Overview

Complete documentation for the Second Brain Database shop pricing system and Razorpay payment integration.

---

## 📊 Current Pricing (Option A: Budget-Friendly)

### Exchange Rate
- **1 INR = 1,000,000 SBD**
- **1 SBD = ₹0.000001**

### Price List

| Item Type | INR Price | SBD Price | Savings (Bundles) |
|-----------|-----------|-----------|-------------------|
| **Themes** | ₹29 | 29,000,000 SBD | - |
| **Animated Avatars** | ₹49 | 49,000,000 SBD | - |
| **Static Avatars** | ₹5 | 5,000,000 SBD | - |
| **Banners** | ₹19 | 19,000,000 SBD | - |
| **Cat Lovers Bundle** | ₹129 | 129,000,000 SBD | Save 55% (₹71) |
| **Dog Lovers Bundle** | ₹129 | 129,000,000 SBD | Save 50% (₹56) |
| **Panda Bundle** | ₹99 | 99,000,000 SBD | Save 50% (₹51) |
| **People Bundle** | ₹129 | 129,000,000 SBD | Great value! |
| **Dark Theme Pack** | ₹119 | 119,000,000 SBD | Save 20% (₹28) |
| **Light Theme Pack** | ₹119 | 119,000,000 SBD | Save 20% (₹28) |

---

## 💳 Payment Methods

### 1. SBD Tokens (Active)
- **Status**: ✅ Fully Implemented
- **Use**: Family members can purchase using shared SBD tokens
- **Process**: Instant, no fees
- **Frontend**: Enabled in Digital Shop

### 2. Razorpay (INR) (Backend Ready)
- **Status**: ⚙️ Backend Implemented, Frontend Pending
- **Use**: Purchase SBD tokens with real money (INR)
- **Process**: Razorpay payment gateway
- **Frontend**: Coming Soon badge

---

## 🔧 Razorpay Integration

### Setup Requirements

1. **Razorpay Account**
   - Sign up at https://razorpay.com
   - Complete KYC verification
   - Get API credentials

2. **Environment Variables**
   ```bash
   # Required
   RAZORPAY_KEY_ID=rzp_test_xxxxx          # Test: rzp_test_, Live: rzp_live_
   RAZORPAY_KEY_SECRET=xxxxx                # Secret key
   RAZORPAY_WEBHOOK_SECRET=xxxxx            # Webhook secret
   
   # Optional
   RAZORPAY_ENVIRONMENT=sandbox             # sandbox or production
   PAYMENT_CURRENCY=INR
   PAYMENT_MIN_AMOUNT=5                     # Minimum ₹5
   PAYMENT_MAX_AMOUNT=10000                 # Maximum ₹10,000
   ```

3. **Webhook Configuration**
   - URL: `https://yourdomain.com/api/payments/webhooks`
   - Events: `payment.captured`, `payment.failed`, `order.paid`
   - Secret: Use `RAZORPAY_WEBHOOK_SECRET`

### Payment Flow

```
User Wants to Buy SBD Tokens
         ↓
1. Select Amount (₹10, ₹50, ₹100, etc.)
         ↓
2. POST /payments/orders
   - Creates Razorpay order
   - Returns order_id, amount
         ↓
3. Frontend shows Razorpay checkout (PENDING)
   - User pays via UPI/Card/NetBanking
         ↓
4. Razorpay processes payment
         ↓
5. Webhook: POST /payments/webhooks
   - Verifies signature
   - Credits SBD tokens to user
   - Logs transaction
         ↓
6. User receives SBD tokens
   - Can now purchase shop items
```

### API Endpoints (Implemented)

#### Create Payment Order
```http
POST /api/payments/orders
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "amount_inr": 100,
  "purpose": "sbd_token_purchase"
}

Response:
{
  "order_id": "order_xxxxx",
  "amount": 100.00,
  "currency": "INR",
  "sbd_equivalent": 100000000.00
}
```

#### Verify Payment
```http
POST /api/payments/verify
Authorization: Bearer {jwt_token}

{
  "order_id": "order_xxxxx",
  "payment_id": "pay_xxxxx",
  "signature": "xxxxx"
}

Response:
{
  "status": "success",
  "transaction_id": "txn_123",
  "sbd_credited": 100000000.00
}
```

#### Webhook Handler
```http
POST /api/payments/webhooks
X-Razorpay-Signature: {signature}

{
  "event": "payment.captured",
  "payload": { ... }
}
```

#### Payment History
```http
GET /api/payments/history
Authorization: Bearer {jwt_token}

Response:
{
  "transactions": [
    {
      "transaction_id": "txn_123",
      "amount_inr": 100.00,
      "amount_sbd": 100000000.00,
      "status": "completed",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 🛡️ Security Features

### Payment Security
- ✅ HMAC SHA256 signature verification
- ✅ Idempotency keys for duplicate prevention
- ✅ Amount verification before crediting
- ✅ Rate limiting on payment endpoints
- ✅ Audit logging for all transactions

### Data Protection
- ✅ No credit card data stored (Razorpay handles)
- ✅ PCI DSS compliant (via Razorpay)
- ✅ Encrypted webhook secrets
- ✅ Secure API key storage

### Fraud Prevention
- ✅ Payment amount verification
- ✅ User authentication required
- ✅ Transaction limits (₹5 - ₹10,000)
- ✅ Suspicious activity monitoring

---

## 📱 Frontend Integration (Pending)

### Digital Shop Updates Needed

1. **Add SBD Formatting**
   ```typescript
   // Already implemented in Family Hub
   import { formatSBDTokens } from '@/lib/utils';
   
   // Display price
   {formatSBDTokens(product.price)} // "29,000,000.00 SBD"
   ```

2. **Update Product Display**
   - Show SBD price prominently
   - Add "₹29" as reference
   - Bundle savings badges

3. **Checkout Flow**
   - SBD payment (active)
   - INR payment (coming soon badge)

4. **Token Purchase Page** (Future)
   - Buy SBD with INR
   - Razorpay integration
   - Transaction history

---

## 🧪 Testing

### Sandbox Testing

1. **Test Credentials**
   ```
   Key ID: rzp_test_xxxxx
   Key Secret: xxxxx
   ```

2. **Test Cards**
   ```
   Success: 4111 1111 1111 1111
   Failure: 4000 0000 0000 0002
   CVV: Any 3 digits
   Expiry: Any future date
   ```

3. **Test UPI**
   ```
   success@razorpay
   failure@razorpay
   ```

### Test Scenarios

- [ ] Create order with ₹100
- [ ] Complete payment successfully
- [ ] Verify SBD tokens credited
- [ ] Test payment failure
- [ ] Test webhook delivery
- [ ] Test refund flow
- [ ] Test duplicate payment prevention

---

## 🚀 Deployment Checklist

### Pre-Production
- [ ] Get production Razorpay credentials
- [ ] Update environment variables
- [ ] Configure webhook URL
- [ ] Test webhook delivery
- [ ] Set up monitoring/alerts
- [ ] Configure rate limits
- [ ] Enable audit logging

### Production
- [ ] Switch to production keys
- [ ] Test with small amount (₹10)
- [ ] Monitor first transactions
- [ ] Set up customer support flow
- [ ] Document refund process

---

## 📈 Revenue Projections

### Scenario: 1,000 Active Users

| Item Type | Avg Price | Monthly Sales | Revenue |
|-----------|-----------|---------------|---------|
| Themes | ₹29 | 200 | ₹5,800 |
| Avatars | ₹5-49 | 500 | ₹15,000 |
| Banners | ₹19 | 150 | ₹2,850 |
| Bundles | ₹99-129 | 100 | ₹11,500 |
| **Total** | - | **950** | **₹35,150/month** |

**Annual**: ~₹4.2 lakhs

### With 10,000 Users
- **Monthly**: ₹3.5 lakhs
- **Annual**: ₹42 lakhs

---

## 🔄 Future Enhancements

### Phase 1 (Current)
- ✅ Budget-friendly pricing
- ✅ SBD token purchases
- ⚙️ Razorpay backend ready

### Phase 2 (Next)
- [ ] Frontend Razorpay integration
- [ ] Token purchase page
- [ ] Transaction history UI
- [ ] Receipt generation

### Phase 3 (Future)
- [ ] Subscription plans
- [ ] Referral rewards
- [ ] Seasonal sales
- [ ] Gift cards
- [ ] Loyalty program

---

## 📞 Support

### For Users
- Payment issues: Check transaction history
- Refunds: Contact support with transaction ID
- Token not credited: Allow 5-10 minutes, then contact support

### For Developers
- Razorpay docs: https://razorpay.com/docs/
- Webhook testing: https://razorpay.com/docs/webhooks/
- API reference: https://razorpay.com/docs/api/

---

## 📝 Change Log

### 2024-11-24
- ✅ Updated pricing to Option A (Budget-Friendly)
- ✅ Added INR equivalent fields
- ✅ Created Razorpay configuration
- ✅ Documented payment flow
- ⚙️ Backend payment integration (in progress)

---

## ⚠️ Important Notes

1. **Test Mode**: Currently using placeholder Razorpay credentials
2. **Frontend**: SBD payments only, INR coming soon
3. **Limits**: ₹5 minimum, ₹10,000 maximum per transaction
4. **Currency**: INR only (international currencies future)
5. **Refunds**: Manual process, contact admin

---

**Last Updated**: 2024-11-24  
**Version**: 1.0  
**Status**: Backend Ready, Frontend Pending
