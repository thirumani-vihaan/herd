import json

new_fixtures = [
    {
        "id": "scam_impersonation_0", 
        "file": "fixtures/screenshots/scam_impersonation_0.png", 
        "sha256": "hash0", 
        "truth": "FALSE", 
        "claim_type": "placement", 
        "strain_group": "placement_fee_scam", 
        "adversarial": None, 
        "institution_name": "Nalanda Institute of Technology", 
        "institution_domain": "nalanda-tech.invalid", 
        "text": "Nalanda Institute Placements\nRegister at http://nalanda-tech-placements.online\nFee Rs 750", 
        "forwarded": True, 
        "frequently_forwarded": False, 
        "visible_time": "10:00", 
        "group": "Class Group", 
        "sender": "+91 91234 56789", 
        "is_fixture": True
    },
    {
        "id": "scam_impersonation_1", 
        "file": "fixtures/screenshots/scam_impersonation_1.png", 
        "sha256": "hash1", 
        "truth": "FALSE", 
        "claim_type": "exam", 
        "strain_group": "exam_fee_scam", 
        "adversarial": None, 
        "institution_name": "Kaveri College of Engineering", 
        "institution_domain": "kaveri-engg.invalid", 
        "text": "Kaveri Exam Fee Payment\nPay via portal: http://kaveri-engg-admin.com/pay", 
        "forwarded": True, 
        "frequently_forwarded": False, 
        "visible_time": "11:00", 
        "group": "Class Group", 
        "sender": "+91 91234 56789", 
        "is_fixture": True
    },
    {
        "id": "scam_impersonation_2", 
        "file": "fixtures/screenshots/scam_impersonation_2.png", 
        "sha256": "hash2", 
        "truth": "FALSE", 
        "claim_type": "scholarship", 
        "strain_group": "scholarship_scam", 
        "adversarial": None, 
        "institution_name": "Sahyadri Institute of Science", 
        "institution_domain": "sahyadri-sci.invalid", 
        "text": "Scholarship for Sahyadri students!\nApply at http://sahyadri-sci-support.in", 
        "forwarded": True, 
        "frequently_forwarded": False, 
        "visible_time": "12:00", 
        "group": "Class Group", 
        "sender": "+91 91234 56789", 
        "is_fixture": True
    },
    {
        "id": "scam_lookalike_0", 
        "file": "fixtures/screenshots/scam_lookalike_0.png", 
        "sha256": "hash3", 
        "truth": "FALSE", 
        "claim_type": "placement", 
        "strain_group": "placement_fee_scam", 
        "adversarial": None, 
        "institution_name": "Nalanda Institute of Technology", 
        "institution_domain": "nalanda-tech.invalid", 
        "text": "Important Placement Notice\nPortal: http://nalanda-tehc.invalid/login", 
        "forwarded": True, 
        "frequently_forwarded": False, 
        "visible_time": "13:00", 
        "group": "Class Group", 
        "sender": "+91 91234 56789", 
        "is_fixture": True
    },
    {
        "id": "scam_lookalike_1", 
        "file": "fixtures/screenshots/scam_lookalike_1.png", 
        "sha256": "hash4", 
        "truth": "FALSE", 
        "claim_type": "exam", 
        "strain_group": "exam_fee_scam", 
        "adversarial": None, 
        "institution_name": "Meridian University", 
        "institution_domain": "meridian-univ.invalid", 
        "text": "Download admit card\nLink: http://meridian-unv.invalid/admit", 
        "forwarded": True, 
        "frequently_forwarded": False, 
        "visible_time": "14:00", 
        "group": "Class Group", 
        "sender": "+91 91234 56789", 
        "is_fixture": True
    }
]

file_path = "fixtures/labels.jsonl"
existing_ids = set()

with open(file_path, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        existing_ids.add(obj["id"])

with open(file_path, "a") as f:
    for fix in new_fixtures:
        if fix["id"] not in existing_ids:
            f.write(json.dumps(fix) + "\n")

print("Added new fixtures.")
