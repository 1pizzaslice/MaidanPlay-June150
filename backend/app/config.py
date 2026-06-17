"""Static business configuration for June One50.

The legacy app kept these values in browser globals. In this rewrite they live
server-side so permissions and stage completion checks cannot be bypassed by a
client edit.
"""

BATCH_CONFIG = {
    "Toddlers": {"coach": "Adi", "employees": ["Sanjana"]},
    "Sub Junior": {"coach": "Daksh", "employees": ["Aryan"]},
    "Junior": {"coach": "Kush", "employees": ["Pranjal"]},
    "Senior": {"coach": "Eeshan", "employees": ["Aryan"]},
}

BATCH_ORDER = ["Toddlers", "Sub Junior", "Junior", "Senior"]
BATCH_REMAP = {"Adult": "Senior", "Adult+": "Senior"}

ORG = {
    "employees": ["Sanjana", "Aryan", "Pranjal"],
    "pnlHead": {"name": "Kush", "role": "Academy P&L Head"},
    "director": {"name": "Amit", "role": "Maidan Director"},
    "founder": {"name": "Akash", "role": "Maidan Co-Founder"},
}

ACCESS_LABEL = {
    "edit": "Edit access",
    "confirm": "Confirm access",
    "view": "Viewer access",
}

ROLE_LABEL = {
    "employee": "Maidan Employee",
    "coach": "Coach",
    "kush": "Academy P&L Head",
    "amit": "Maidan Director",
    "akash": "Maidan Co-Founder",
    "admin": "Administrator",
    "viewer": "Viewer",
}

DEFAULT_SEED_PASSWORD = "MaidanPlay@2026"

USERS = [
    {"name": "Vasu", "email": "yuvrajchawla@maidanplay.com", "mobile": "9810575510", "access": "edit", "role": "amit"},
    {"name": "Athar", "email": "mdathar@maidanplay.com", "mobile": "", "access": "edit", "role": "kush"},
    {"name": "Kush", "email": "kushagrasarin@maidanplay.com", "mobile": "9599126646", "access": "edit", "role": "kush"},
    {"name": "Amit", "email": "amitmishra@maidanplay.com", "mobile": "7703832814", "access": "edit", "role": "amit"},
    {"name": "Akash", "email": "akashsahay@maidanplay.com", "mobile": "8826204541", "access": "edit", "role": "akash"},
    {"name": "Abhimanyu", "email": "abhimanyusingh@maidanplay.com", "mobile": "9013603656", "access": "edit", "role": "admin"},
    {"name": "Ruchir", "email": "ruchirprasoon@maidanplay.com", "mobile": "9939180058", "access": "edit", "role": "admin"},
]

SUPER = ["Akash", "Abhimanyu", "Ruchir"]

STAGE = {
    "DRAFT": "draft",
    "AMIT": "pending_amit",
    "AKASH": "pending_akash",
    "DONE": "approved",
}

STAGE_LABEL = {
    "draft": "Open",
    "pending_amit": "Pending Amit",
    "pending_akash": "Pending Akash",
    "approved": "Enrolled",
}

CONFIRM_FIELDS = [
    {"key": "first", "label": "Player First Name", "src": "first", "o3": "Corrected name"},
    {"key": "last", "label": "Player Last Name", "src": "last", "o3": "Corrected name"},
    {"key": "dob", "label": "Date of Birth", "src": "dob", "o3": "Corrected DOB", "input": "date"},
    {
        "key": "gender",
        "label": "Gender",
        "src": "gender",
        "o3": "Corrected gender",
        "input": "select",
        "choices": ["Male", "Female", "Other"],
    },
    {"key": "school", "label": "School Name", "src": "school", "o3": "Corrected school", "input": "school"},
    {"key": "pincode", "label": "Home Pincode", "src": "pincode", "o3": "Corrected pincode", "input": "num"},
    {
        "key": "parent",
        "label": "Parent / Guardian Name",
        "src": "parent",
        "o3": "Corrected name",
        "extra": "Relationship (e.g. Father)",
    },
    {"key": "phone", "label": "WhatsApp Number", "src": "phone", "o3": "Corrected number", "input": "num"},
    {"key": "email", "label": "Email", "src": "email", "o3": "Corrected email"},
    {
        "key": "jersey",
        "label": "Jersey Size",
        "src": "jersey",
        "o3": "Corrected size",
        "input": "select",
        "choices": ["XXS", "XS", "S", "M", "L", "XL", "XXL"],
    },
    {"key": "cup", "label": "Cup of Nations", "src": "cup", "o1": "Yes", "o2": "No", "o3": "Final confirmation"},
    {"key": "amount", "label": "Total Amount", "src": "amount", "o3": "Corrected amount", "input": "num"},
    {"key": "age", "label": "Age", "src": "age"},
]

AMIT_FIELDS = [
    {"key": "ytdJersey", "label": "YTD May 2026 - No Dues: Jersey", "type": "cleared"},
    {"key": "ytdPayment", "label": "YTD May 2026 - No Dues: Payment", "type": "cleared"},
    {"key": "ytdOthers", "label": "YTD May 2026 - Others No Dues: Payment", "type": "cleared"},
    {"key": "scholarshipFlag", "label": "Scholarship", "type": "yesno"},
    {"key": "scholarshipFees", "label": "Scholarship fees", "type": "value", "when": "scholarshipFlag=Yes"},
    {"key": "oneVone", "label": "1v1 Enrolled", "type": "yesno"},
    {"key": "oneVoneRev", "label": "Additional 1v1 revenue", "type": "value", "when": "oneVone=Yes"},
    {"key": "prominence", "label": "Prominence", "type": "yesno"},
    {"key": "prominenceFees", "label": "Prominence student fees", "type": "value", "when": "prominence=Yes"},
    {"key": "planMonths", "label": "Plan month quantum", "type": "choice", "choices": ["1", "3", "6"]},
    {"key": "academyFee", "label": "Academy fee", "type": "value"},
]

AKASH_FIELDS = [
    {"key": "feeReceived", "label": "Fee value received", "type": "value"},
    {"key": "invoiceShared", "label": "Invoice shared", "type": "yesno"},
    {
        "key": "paymentType",
        "label": "Payment type",
        "type": "select",
        "choices": ["Cash", "Cheque", "Credit Card", "Debit Card", "UPI", "Others"],
    },
    {"key": "cashFeeValue", "label": "Cash fee value", "type": "value", "when": "paymentType=Cash"},
    {"key": "noDuesMail", "label": "No-dues mail shared", "type": "yesno"},
    {"key": "legalSigned", "label": "Legal policies signed", "type": "yesno"},
    {"key": "kitDelivered", "label": "Onboarding Kit Delivered", "type": "yesno", "greenOn": "Yes"},
]

GREEN_TARGET = 150

DETAIL_FIELDS = [
    "first",
    "last",
    "dob",
    "gender",
    "school",
    "parent",
    "phone",
    "email",
    "jersey",
    "cup",
    "amount",
    "age",
]

KYP_FIELDS = [
    {"key": "position", "label": "Preferred Position", "type": "choice", "choices": ["GK", "DEF", "MID", "ATT"]},
    {
        "key": "club",
        "label": "Favourite Club Team",
        "type": "select",
        "choices": [
            "Real Madrid",
            "Barcelona",
            "Atletico Madrid",
            "Manchester City",
            "Arsenal",
            "Liverpool",
            "Manchester United",
            "Chelsea",
            "Tottenham Hotspur",
            "Bayern Munich",
            "Bayer Leverkusen",
            "Borussia Dortmund",
            "RB Leipzig",
            "Paris Saint-Germain",
            "Inter Milan",
            "AC Milan",
            "Juventus",
            "Napoli",
            "Benfica",
            "Porto",
        ],
    },
    {"key": "foot", "label": "Preferred Foot", "type": "choice", "choices": ["Right", "Left"]},
    {"key": "ig", "label": "Active on Instagram", "type": "yesno"},
    {
        "key": "favPlayer",
        "label": "Current Favourite Player",
        "type": "select",
        "choices": [
            "Lionel Messi",
            "Cristiano Ronaldo",
            "Kylian Mbappe",
            "Erling Haaland",
            "Vinicius Junior",
            "Jude Bellingham",
            "Kevin De Bruyne",
            "Mohamed Salah",
            "Harry Kane",
            "Rodri",
            "Robert Lewandowski",
            "Neymar Jr",
            "Lautaro Martinez",
            "Bukayo Saka",
            "Phil Foden",
            "Florian Wirtz",
            "Jamal Musiala",
            "Lamine Yamal",
            "Pedri",
            "Ruben Dias",
            "Virgil van Dijk",
            "Antoine Griezmann",
            "Luka Modric",
            "Toni Kroos",
            "Son Heung-min",
            "Federico Valverde",
            "Martin Odegaard",
            "Declan Rice",
            "Achraf Hakimi",
            "Rafael Leao",
        ],
    },
    {"key": "level", "label": "Football Current Level", "type": "choice", "choices": ["Semi Pro", "Pro"]},
]

STUDENT_COLUMNS = [
    "id",
    "first",
    "last",
    "batch",
    "dob",
    "gender",
    "school",
    "pincode",
    "parent",
    "phone",
    "email",
    "jersey",
    "cup",
    "amount",
    "age",
]
