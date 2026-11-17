"""Evidence-only deterministic draft engine; optional LLM generation comes later."""
from app.domains.catalog.service import get_value
from app.models import Product, Keyword

LABELS_ZH = {"thickness_mm":"厚度（毫米）","finishes":"表面处理","applications":"适用场景","origin":"产地"}
LABELS_EN = {"thickness_mm":"Thickness (mm)","finishes":"Finishes","applications":"Applications","origin":"Origin"}

def safe_string(value):
    if isinstance(value,list):
        return "、".join(map(str,value))
    return str(value)

def generate(product: Product, keyword: Keyword, verified_facts: dict[str, dict]) -> dict:
    locale = keyword.locale
    primary = "title_en" if locale == "en-US" else "title_zh"
    snapshot = verified_facts
    verified = set(snapshot)
    name = (getattr(product,primary) or "").strip()
    if primary not in verified:
        name = keyword.phrase  # Do not assert unverified product identity
    title = f"{name} | {keyword.phrase}"
    if locale == "zh-CN":
        description = f"围绕“{keyword.phrase}”整理的已核实石材资料；具体规格、供货能力和报价请以实际询盘为准。"
        lines = [f"# {title}","", "本页展示已核实的产品资料，便于采购需求评估。", "", "## 已核实的产品信息", ""]
        labels = LABELS_ZH
    else:
        description = f"Verified stone product information relevant to {keyword.phrase}. Request a quote for availability and project specifications."
        lines = [f"# {title}","", "This page lists verified product information for purchase planning.", "", "## Verified product facts", ""]
        labels = LABELS_EN
    if primary in snapshot:
        lines.append(f"- {'产品' if locale=='zh-CN' else 'Product'}: {name}")
    if "stone_type" in snapshot:
        lines.append(f"- {'材质' if locale=='zh-CN' else 'Material'}: {product.stone_type}")
    for field, fact in snapshot.items():
        if not field.startswith("properties."):
            continue
        key = field.split(".",1)[1]
        lines.append(f"- {labels.get(key,key)}: {safe_string(fact['value'])}")
    lines.extend(["", "## 询盘" if locale == "zh-CN" else "## Enquiry", "",
                  "欢迎提供项目数量、尺寸与交付要求，具体报价及供货情况以人工确认为准。" if locale == "zh-CN" else
                  "Share the project quantity, dimensions and delivery requirements. Pricing and availability require human confirmation."])
    return {"title":title,"description":description,"body":"\n".join(lines),"evidence_snapshot":snapshot}

def qa_blockers(content) -> list[str]:
    snapshot = content.evidence_snapshot or {}
    blockers=[]
    identity = "title_en" if content.locale == "en-US" else "title_zh"
    if identity not in snapshot:
        blockers.append(f"Missing verified product identity: {identity}")
    if "stone_type" not in snapshot:
        blockers.append("Missing verified stone type")
    if not any(k.startswith("properties.") for k in snapshot):
        blockers.append("No verified distinctive product property")
    if not all(v.get("source") for v in snapshot.values()):
        blockers.append("Some verified facts have no evidence reference")
    if not content.title or not content.body:
        blockers.append("Empty title or body")
    if len(content.title) > 120:
        blockers.append("Title too long for internal content quality policy (120 chars)")
    return blockers
