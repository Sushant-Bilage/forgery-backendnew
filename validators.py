import re
from datetime import datetime

def _validate_dob(d):
    try:
        datetime.strptime(d.replace("-","/"),"%d/%m/%Y")
        return True,""
    except:
        return False,"Invalid DOB"

def _validate_name(n):
    if not n or len(n.strip())<3:
        return False,"Invalid name"
    return True,""

def validate_pan(d):
    score=100; issues=[]
    pan=d.get("id_number","")

    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]",pan):
        issues.append("Invalid PAN"); score-=40

    ok,msg=_validate_name(d.get("name",""))
    if not ok: issues.append(msg); score-=20

    ok,msg=_validate_dob(d.get("dob",""))
    if not ok: issues.append(msg); score-=20

    if not d.get("father_name"):
        issues.append("Father name missing"); score-=5

    return max(0,score),issues

def validate_aadhaar(d):
    score=100; issues=[]
    uid=re.sub(r"\D","",d.get("id_number",""))

    penalty=0
    if len(uid)!=12:
        issues.append("Invalid Aadhaar"); penalty+=50
    else:
        if uid[0] in "01": penalty+=15
    score-=min(penalty,60)

    ok,msg=_validate_name(d.get("name",""))
    if not ok: issues.append(msg); score-=20

    return max(0,score),issues

def validate_marks_card(d):
    score=100; issues=[]
    sub=d.get("subjects",[])
    marks=d.get("marks",[])
    total=d.get("total",0)

    if len(sub)!=len(marks):
        issues.append("Mismatch subjects/marks"); score-=30

    try:
        s=sum(int(x) for x in marks)
        if abs(s-total)>2:
            issues.append("Total mismatch"); score-=30
    except:
        issues.append("Invalid marks"); score-=20

    if len(set(marks))==1:
        issues.append("All marks same"); score-=10

    return max(0,score),issues

def run_validation(d):
    t=d.get("doc_type","unknown")
    if t=="pan": return validate_pan(d)
    if t=="aadhaar": return validate_aadhaar(d)
    if t=="marks": return validate_marks_card(d)
    return 30,["Unknown document"]