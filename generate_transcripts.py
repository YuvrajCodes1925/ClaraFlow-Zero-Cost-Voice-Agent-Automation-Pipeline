import os

ACCOUNTS = [
    {
        "id": "acct_001",
        "company": "Apex Heating and Air",
        "industry": "HVAC",
        "industry_services": ["heating", "cooling", "indoor air quality", "generator repair"],
        "sw1": "ServiceTitan", "sw2": "FieldEdge",
        "address1": "123 Cold Breeze Lane, Dallas, TX 75201",
        "address2": "456 Warm Sun Blvd, Dallas, TX 75202",
        "tz": "Central Time",
        "h1": "7 AM to 6 PM", "h2": "extend to 7 PM on Friday",
        "em1": "no heat in winter", "em2": "no AC in summer", "em3": "sparking wires", "em4": "refrigerant leak",
        "c1_name": "John Smith", "c1_phone": "214-555-0100",
        "c2_name": "Jane Doe", "c2_phone": "214-555-0101",
        "c3_name": "Mike Johnson", "c3_phone": "214-555-0102"
    },
    {
        "id": "acct_002",
        "company": "Flow Right Plumbing",
        "industry": "plumbing",
        "industry_services": ["drain cleaning", "water heater installation", "leak repair"],
        "sw1": "ServiceTrade", "sw2": "Housecall Pro",
        "address1": "789 Pipe Street, Denver, CO 80202",
        "address2": "101 Faucet Way, Denver, CO 80203",
        "tz": "Mountain Time",
        "h1": "8 AM to 5 PM", "h2": "add Saturday 9 AM to 1 PM",
        "em1": "burst pipe", "em2": "flooding", "em3": "sewage backup", "em4": "no water at all",
        "c1_name": "Rick Sanchez", "c1_phone": "303-555-0200",
        "c2_name": "Morty Smith", "c2_phone": "303-555-0201",
        "c3_name": "Summer Smith", "c3_phone": "303-555-0202"
    },
    {
        "id": "acct_003",
        "company": "Volt Master Electrical",
        "industry": "electrical",
        "industry_services": ["panel upgrades", "ev charger installation", "wiring repair"],
        "sw1": "Housecall Pro", "sw2": "Jobber",
        "address1": "222 Spark Ave, Seattle, WA 98101",
        "address2": "222 Spark Ave, Seattle, WA 98101", # no address change, different changes
        "tz": "Pacific Time",
        "h1": "6 AM to 4 PM", "h2": "open until 5 PM on Monday",
        "em1": "power outage", "em2": "electrical fire smell", "em3": "sparking panel", "em4": "exposed live wires",
        "c1_name": "Walter White", "c1_phone": "206-555-0300",
        "c2_name": "Jesse Pinkman", "c2_phone": "206-555-0301",
        "c3_name": "Saul Goodman", "c3_phone": "206-555-0302"
    },
    {
        "id": "acct_004",
        "company": "Frost Bite Refrigeration",
        "industry": "refrigeration",
        "industry_services": ["commercial freezer repair", "walk-in cooler maintenance", "ice machine service"],
        "sw1": "FieldEdge", "sw2": "ServiceTitan",
        "address1": "555 Chill Blvd, Chicago, IL 60601",
        "address2": "777 Freeze Road, Chicago, IL 60605",
        "tz": "Central Time",
        "h1": "Open 8 AM to 6 PM Monday through Friday and Saturday 9 AM to 12 PM",
        "h2": "Saturday hours removed",
        "em1": "refrigeration down", "em2": "freezer temp rising", "em3": "compressor failure", "em4": "spoiling inventory risk",
        "c1_name": "Tony Soprano", "c1_phone": "312-555-0400",
        "c2_name": "Paulie Walnuts", "c2_phone": "312-555-0401",
        "c3_name": "Silvio Dante", "c3_phone": "312-555-0402"
    },
    {
        "id": "acct_005",
        "company": "Safe Shield Fire Protection",
        "industry": "fire protection",
        "industry_services": ["sprinkler installation", "fire alarm testing", "hood suppression"],
        "sw1": "Jobber", "sw2": "ServiceTrade",
        "address1": "999 Flame Street, Atlanta, GA 30303",
        "address2": "999 Flame Street, Atlanta, GA 30303",
        "tz": "Eastern Time",
        "h1": "9 AM to 5 PM Monday through Friday", "h2": "extended closing to 6 PM on Tuesday",
        "em1": "sprinkler discharge", "em2": "alarm system error", "em3": "tag out", "em4": "panel beeping",
        "c1_name": "Michael Scott", "c1_phone": "404-555-0500",
        "c2_name": "Dwight Schrute", "c2_phone": "404-555-0501",
        "c3_name": "Jim Halpert", "c3_phone": "404-555-0502"
    }
]

demo_template = """Account: {id}

AGENT: Hello, thanks for taking the time to set up your account. I'm ready to capture your business details.
CLIENT: Sure. We're {company}, we do {industry}. 
AGENT: Great. What are your core services?
CLIENT: We mainly do {svc0}, {svc1}, and {svc2}.
AGENT: Got it. What's the main office address?
CLIENT: It's {address1}.
AGENT: And your regular operating hours?
CLIENT: We are open Monday through Friday, from {h1}. We are in {tz}.
AGENT: Perfect. If someone calls during those hours, how should Clara handle it?
CLIENT: Just greet them, ask what they need, and say "Let me connect you right now" to transfer to our office line at 800-555-1000. Give it about 4 rings. If nobody answers, take a message with their name and callback number.
AGENT: Sounds good. What about after hours? How do we determine an emergency?
CLIENT: An emergency is if there's {em1}, {em2}, or {em3}. 
AGENT: Understood. If it's an emergency, what's the routing sequence?
CLIENT: First call {c1_name} at {c1_phone}. Give them 30 seconds to answer. If they don't, try {c2_name} at {c2_phone}.
AGENT: What if neither answers?
CLIENT: Leave a voicemail telling the customer we'll call back within 30 minutes. Also remind them to call 911 if it's life-threatening.
AGENT: Got it. And for non-emergencies after hours?
CLIENT: Just take their name and phone number and follow up next business day. Tell them we'll call by 9 AM.
AGENT: What software do you use for scheduling?
CLIENT: We use {sw1}, but we have a strict rule: Do not create jobs or tickets in {sw1} directly. Just send us the info.
AGENT: Any particular tone or routing restrictions?
CLIENT: Please remain warm and calm. Also, never dispatch for maintenance renewals after hours.
AGENT: Thank you! All set.
"""

onboarding_template = """Account: {id}

AGENT: Hi again! Tell me what's changing with {company}.
CLIENT: Hey! We have a few updates. First, our number for {c1_name} changed to {c3_phone}.
AGENT: Updated. What else?
CLIENT: We have a new service line: {svc3}. We're also expanding emergencies: now we add {em4} as an emergency.
AGENT: Great. Did your address or hours change?
CLIENT: Yes, {address_change_text}. Also for our hours, we {h2_change_text}.
AGENT: Got it. Any software updates?
CLIENT: Yes, we switched from {sw1} to {sw2}. Same rule applies: do not create jobs in {sw2} directly.
AGENT: And I'll note your new routing rule: commercial clients route differently now after hours. I've got this all logged!
"""

os.makedirs(r"c:\\Users\\Yuvraj Singh\\Downloads\\files\\clara-pipeline\\data\\demo_calls", exist_ok=True)
os.makedirs(r"c:\\Users\\Yuvraj Singh\\Downloads\\files\\clara-pipeline\\data\\onboarding_calls", exist_ok=True)

for acct in ACCOUNTS:
    demo_content = demo_template.format(
        id=acct["id"], company=acct["company"], industry=acct["industry"],
        svc0=acct["industry_services"][0], svc1=acct["industry_services"][1], svc2=acct["industry_services"][2],
        address1=acct["address1"], h1=acct["h1"], tz=acct["tz"],
        em1=acct["em1"], em2=acct["em2"], em3=acct["em3"],
        c1_name=acct["c1_name"], c1_phone=acct["c1_phone"],
        c2_name=acct["c2_name"], c2_phone=acct["c2_phone"],
        sw1=acct["sw1"]
    )
    with open(f"c:\\Users\\Yuvraj Singh\\Downloads\\files\\clara-pipeline\\data\\demo_calls\\{acct['id']}_demo.txt", "w") as f:
        f.write(demo_content)

    addr_text = f"our new address is {acct['address2']}" if acct['address1'] != acct['address2'] else "no address change"
    h2_text = acct['h2']
    
    onboarding_content = onboarding_template.format(
        id=acct["id"], company=acct["company"],
        c1_name=acct["c1_name"], c3_phone=acct["c3_phone"],
        svc3=acct["industry_services"][3] if len(acct["industry_services"]) > 3 else "general contracting",
        em4=acct["em4"],
        address_change_text=addr_text, h2_change_text=h2_text,
        sw1=acct["sw1"], sw2=acct["sw2"]
    )
    with open(f"c:\\Users\\Yuvraj Singh\\Downloads\\files\\clara-pipeline\\data\\onboarding_calls\\{acct['id']}_onboarding.txt", "w") as f:
        f.write(onboarding_content)

print("Generated all files!")
