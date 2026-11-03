"""
Centralized choices for the Restaurant Portal project.
"""

# ====================================================
# User Roles
# ====================================================
USER_ROLES = (
    ('CUSTOMER', 'Customer'),
    ('RESTAURANT_OWNER', 'Restaurant Owner'),
    ('RESTAURANT_STAFF', 'Restaurant Staff'),
    ('DELIVERY_STAFF', 'Delivery Staff'),
    ('SUPER_ADMIN', 'Super Admin'),
)

# ====================================================
# Staff Roles (within a restaurant)
# ====================================================
STAFF_ROLES = (
    ('ADMIN', 'Admin'),
    ('MANAGER', 'Manager'),
    ('CASHIER', 'Cashier'),
    ('KITCHEN_STAFF', 'Kitchen Staff'),
    ('DELIVERY_STAFF', 'Delivery Staff'),
    ('STOCK_STAFF', 'Stock Staff'),
)

# ====================================================
# Gender
# ====================================================
GENDER_CHOICES = (
    ('MALE', 'Male'),
    ('FEMALE', 'Female'),
    ('OTHER', 'Other'),
    ('NOT_SPECIFIED', 'Not Specified'),
)

# ====================================================
# Orders
# ====================================================
ORDER_TYPES = (
    ('PICKUP', 'Pickup'),
    ('DELIVERY', 'Delivery'),
    ('DINE_IN', 'Dine In'),
)

ORDER_STATUS = (
    ('PLACED', 'Order Placed'),
    ('CONFIRMED', 'Order Confirmed'),
    ('PREPARING', 'Preparing'),
    ('READY', 'Ready'),
    ('DISPATCHED', 'Dispatched'),
    ('OUT_FOR_DELIVERY', 'Out for Delivery'),
    ('DELIVERED', 'Delivered'),
    ('CANCELLED', 'Cancelled'),
    ('REFUNDED', 'Refunded'),
)

PAYMENT_STATUS = (
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
    ('REFUNDED', 'Refunded'),
)

# ====================================================
# Menu Customizations
# ====================================================
CUSTOMIZATION_TYPES = (
    ('SINGLE_SELECT', 'Single Select'),
    ('MULTIPLE_SELECT', 'Multiple Select'),
    ('TEXT_INPUT', 'Text Input'),
)

# ====================================================
# Payments
# ====================================================
PAYMENT_METHODS = (
    ('CREDIT_CARD', 'Credit Card'),
    ('DEBIT_CARD', 'Debit Card'),
    ('APPLE_PAY', 'Apple Pay'),
    ('GOOGLE_PAY', 'Google Pay'),
    ('PAYPAL', 'PayPal'),
    ('STRIPE', 'Stripe'),
    ('CASH_ON_DELIVERY', 'Cash on Delivery'),
    ('CASH_AT_RESTAURANT', 'Cash at Restaurant'),
)

PAYMENT_GATEWAYS = (
    ('STRIPE', 'Stripe'),
    ('PAYPAL', 'Paypal'),
    ('RAZORPAY', 'Razorpay'),
    ('LOCAL', 'Local'),
)

# ====================================================
# Kitchen Status
# ====================================================
KITCHEN_STATUS = (
    ('NEW', 'New'),
    ('ACCEPTED', 'Accepted'),
    ('PREPARING', 'Preparing'),
    ('READY', 'Ready'),
    ('COLLECTED', 'Collected'),
)

# ====================================================
# Delivery Status
# ====================================================
DELIVERY_STATUS = (
    ('PENDING', 'Pending'),
    ('ASSIGNED', 'Assigned'),
    ('PICKED_UP', 'Picked Up'),
    ('IN_TRANSIT', 'In Transit'),
    ('DELIVERED', 'Delivered'),
    ('CANCELLED', 'Cancelled'),
)

# ====================================================
# Support
# ====================================================
TICKET_CATEGORIES = (
    ('ORDER_ISSUE', 'Order Issue'),
    ('DELIVERY_ISSUE', 'Delivery Issue'),
    ('PAYMENT_ISSUE', 'Payment Issue'),
    ('MISSING_ITEMS', 'Missing Items'),
    ('INCORRECT_ITEMS', 'Incorrect Items'),
    ('QUALITY_ISSUE', 'Quality Issue'),
    ('REFUND_REQUEST', 'Refund Request'),
    ('GENERAL_INQUIRY', 'General Inquiry'),
    ('OTHER', 'Other'),
)

TICKET_PRIORITY = (
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('URGENT', 'Urgent'),
)

TICKET_STATUS = (
    ('OPEN', 'Open'),
    ('IN_PROGRESS', 'In Progress'),
    ('WAITING_FOR_CUSTOMER', 'Waiting for Customer'),
    ('WAITING_FOR_RESTAURANT', 'Waiting for Restaurant'),
    ('RESOLVED', 'Resolved'),
    ('CLOSED', 'Closed'),
)

MESSAGE_TYPES = (
    ('CUSTOMER_MESSAGE', 'Customer Message'),
    ('STAFF_MESSAGE', 'Staff Message'),
)