from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from app.anatomy.router import resolve_profile_model, route_study
from app.medrax_adapter.interfaces import AgentOrchestrator, OutputNormalizer, demo_medrax_tools
from app.models.schemas import (
    AnalysisInput,
    AnalysisResult,
    AnatomyRoute,
    Annotation,
    AnnotationOriginalState,
    AnnotationSource,
    AnnotationTransformMetadata,
    Coordinate,
    Finding,
    ImageQuality,
    ModelTrace,
    Report,
    ResultCard,
    SystematicReading,
)
from app.results.composer import compose_result_cards
from app.results.differential import build_differential_assistance
from app.runtime.adapters import ollama_chat, ollama_vision, require_allowed_endpoint
from app.vision.torchxrayvision_classifier import is_torchxrayvision_model, run_torchxrayvision_classifier
from app.vision.ultralytics_detector import run_msk_fracture_detector


BODY_TEMPLATES = {
    "chest": "Chest X-ray",
    "cxr": "Chest X-ray",
    "thorax": "Chest X-ray",
    "abdomen": "Abdomen X-ray",
    "kub": "Abdomen X-ray",
    "pelvis": "MSK/orthopedic X-ray",
    "hip": "MSK/orthopedic X-ray",
    "shoulder": "MSK/orthopedic X-ray",
    "clavicle": "MSK/orthopedic X-ray",
    "elbow": "MSK/orthopedic X-ray",
    "humerus": "MSK/orthopedic X-ray",
    "forearm": "MSK/orthopedic X-ray",
    "radius": "MSK/orthopedic X-ray",
    "ulna": "MSK/orthopedic X-ray",
    "knee": "MSK/orthopedic X-ray",
    "femur": "MSK/orthopedic X-ray",
    "tibia": "MSK/orthopedic X-ray",
    "fibula": "MSK/orthopedic X-ray",
    "ankle": "MSK/orthopedic X-ray",
    "foot": "MSK/orthopedic X-ray",
    "hand": "MSK/orthopedic X-ray",
    "wrist": "MSK/orthopedic X-ray",
    "spine": "Spine X-ray",
    "cervical": "Spine X-ray",
    "thoracic": "Spine X-ray",
    "lumbar": "Spine X-ray",
    "sacrum": "Spine X-ray",
    "skull": "Skull/facial X-ray",
    "facial": "Skull/facial X-ray",
    "sinus": "Skull/facial X-ray",
}


CXR_REFERENCE_PRIORS = [
    "For suspected pulmonary TB on CXR, upper-lobe consolidation/opacity is a relevant pattern, but it is not specific and can overlap with bacterial pneumonia or scarring.",
    "Only call cavitation when a definite gas/lucent focus about 1 cm or larger with a visible wall/rim is seen inside lung parenchyma, consolidation, nodule, or fibrotic change; if uncertain, say no definite cavitation.",
    "Cavitation with surrounding consolidation is more concerning for active infection/TB, but CXR alone cannot confirm TB.",
    "Absence of definite cavitation on CXR lowers confidence for cavitary TB but does not exclude active TB, pneumonia, or other infection.",
    "Tree-in-bud is primarily a CT pattern; do not use absence or presence of tree-in-bud as a plain CXR criterion and do not mention it in CXR impressions.",
    "Apical fibrosis, volume loss, and calcified granulomas can fit healed/inactive TB; distinguish these from active airspace opacity when possible.",
    "Volume loss, hilar distortion, pleural thickening, or stable apical fibrotic opacity support scarring/healed disease more than acute consolidation.",
    "Always preserve laterality and zone, and separate observation from differential diagnosis.",
    "Keep the workflow X-ray/radiograph focused; mention other modalities only as clinician-directed follow-up, not as an automatic next step.",
]


CXR_SYSTEMATIC_REVIEW = [
    "Adequacy/projection: identify PA/AP/lateral/portable if possible; check rotation, inspiration, penetration, motion/artifact, and prior comparison.",
    "A - Airway: trachea, carina, main bronchi, hila, and mediastinal shift.",
    "B - Breathing: right and left lungs by zones including apices; lung volume, focal opacity/consolidation, interstitial pattern, nodules, pneumothorax, and pleura.",
    "C - Cardiac/circulation: cardiac size/contours, mediastinum, hila, vascular congestion, and edema pattern.",
    "D - Diaphragm: hemidiaphragm position, costophrenic angles, subdiaphragmatic free air, and basal review areas.",
    "E/F - Everything else/failure: bones, soft tissues, visible upper abdomen, devices/lines/tubes, pulmonary edema/heart failure signs, and clinically important negatives.",
]


ORTHOPEDIC_SYSTEMATIC_REVIEW = [
    "Adequacy: confirm the imaged side/body part, adequate penetration, and at least two orthogonal views when available.",
    "Alignment: assess joint congruity, dislocation/subluxation, long-axis alignment, and compare expected anatomic relationships.",
    "Bones: trace the full cortex of every visible bone; look for fracture lines, cortical step-off, impaction, lytic/sclerotic change, and periosteal reaction.",
    "Cartilage/joints: review joint spaces, intra-articular extension, widening that may imply ligamentous injury, degenerative change, and effusion clues.",
    "Soft tissues: look for swelling, fat-pad signs, gas, foreign body, calcification, and indirect signs of occult fracture.",
    "If a fracture is suspected, describe side, bone, proximal/mid/distal location, intra-articular extension, fracture-line pattern, displacement/apposition, angulation, shortening/distraction, comminution, and dislocation. Open/closed and neurovascular status are clinical facts; do not infer them from X-ray alone.",
]


ABDOMEN_SYSTEMATIC_REVIEW = [
    "Adequacy/projection: identify supine/upright/decubitus/KUB if possible; check coverage from diaphragms to pelvis when relevant, exposure, motion, and prior comparison.",
    "Bowel gas pattern: assess small and large bowel caliber, distribution, obstruction pattern, ileus pattern, rectal gas, and air-fluid levels if upright/decubitus is available.",
    "Free air/extra-luminal gas: review subdiaphragmatic region, Rigler-type clues, and soft tissue planes when technically assessable.",
    "Calcifications/opacities: look for renal/ureteric/bladder stones, gallstones when visible, vascular calcification, phleboliths, and abnormal masses/opacities.",
    "Bones/soft tissues/devices: review spine, pelvis, hips, soft tissues, surgical clips, tubes, stents, and foreign bodies.",
    "Keep limitations clear: many abdominal conditions are nonspecific on plain radiographs and require clinical correlation.",
]


GENERAL_XRAY_SYSTEMATIC_REVIEW = [
    "Start with indication, body part, projection/technique, image quality, and comparison if available.",
    "Use an anatomic checklist before diagnosis: review visible bones, joints, soft tissues, devices/foreign bodies, and region-specific organs.",
    "Separate objective observations from interpretation; preserve laterality, location, size/extent when visible, uncertainty, and important negatives.",
]


PROFESSIONAL_REPORTING_PRINCIPLES = [
    "Use a radiology report structure: indication, technique/projection, comparison, findings, impression/conclusion, and recommendations only when they follow from the imaging question.",
    "Make findings objective and concise; make the impression answer the clinical question and prioritize the most important abnormality first.",
    "Use standardized radiology language and consistent sectioning; avoid hedging when the observation is clear, but use uncertain/candidate wording when evidence is limited.",
    "Include pertinent negatives and limitations that affect confidence.",
    "Flag urgent/actionable findings for clinician review, while keeping this prototype non-diagnostic and requiring radiologist/physician verification.",
]


def infer_body_region(metadata: dict[str, Any], filename: str | None, custom_prompt: str = "") -> str:
    return str(route_study(metadata, filename, custom_prompt)["body_region"])


def _is_chest_region(body_region: str) -> bool:
    return body_region.lower() == "chest x-ray"


def _is_orthopedic_region(body_region: str) -> bool:
    text = body_region.lower()
    return "msk" in text or "orthopedic" in text or "spine" in text or "skull" in text or "facial" in text


def _is_abdomen_region(body_region: str) -> bool:
    return body_region.lower() == "abdomen x-ray"


def _bullet_text(items: list[str]) -> str:
    return " ".join(f"- {item}" for item in items)


def _systematic_review_items(body_region: str) -> list[str]:
    if _is_chest_region(body_region):
        return CXR_SYSTEMATIC_REVIEW
    if _is_orthopedic_region(body_region):
        return ORTHOPEDIC_SYSTEMATIC_REVIEW
    if _is_abdomen_region(body_region):
        return ABDOMEN_SYSTEMATIC_REVIEW
    return GENERAL_XRAY_SYSTEMATIC_REVIEW


def _systematic_review_text(body_region: str) -> str:
    return _bullet_text(_systematic_review_items(body_region))


def _professional_reporting_text() -> str:
    return _bullet_text(PROFESSIONAL_REPORTING_PRINCIPLES)


def quality_from_image(image_path: str | None) -> ImageQuality:
    if not image_path:
        return ImageQuality(score=0.2, exposure="unknown", positioning="unknown", limitations=["Tidak ada gambar aktif."])
    with Image.open(image_path) as img:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        mean, contrast = stat.mean[0], stat.stddev[0]
    exposure = "adequate"
    limitations = []
    if mean < 35:
        exposure = "underexposed"
        limitations.append("Gambar tampak gelap; detail jaringan mungkin terbatas.")
    elif mean > 220:
        exposure = "overexposed"
        limitations.append("Gambar tampak sangat terang; detail mungkin terbatas.")
    if contrast < 18:
        limitations.append("Kontras rendah; confidence AI diturunkan.")
    score = max(0.1, min(0.95, 0.55 + (contrast / 120) - (0.12 if limitations else 0)))
    return ImageQuality(score=round(score, 2), exposure=exposure, positioning="not fully assessed", limitations=limitations)


def systematic_template(body_region: str, quality: ImageQuality, custom_prompt: str) -> SystematicReading:
    limitation = "Mode demo/fallback: belum ada model vision klinis aktif; hasil harus diverifikasi radiolog/dokter."
    if custom_prompt:
        limitation += " Instruksi tambahan pengguna dipakai sebagai konteks, bukan bukti klinis mandiri."
    base = {
        "body_region": body_region,
        "adequacy": f"Kualitas gambar {quality.exposure}; skor kualitas perkiraan {quality.score:.2f}.",
        "view_projection": "Proyeksi belum dapat dipastikan otomatis kecuali tersedia pada metadata DICOM.",
        "alignment_anatomy": "Evaluasi anatomi mengikuti checklist sistematis sesuai area; aktifkan model VLM/MedRAX untuk detail organ/spesifik.",
        "soft_tissue": "Tidak ada temuan jaringan lunak spesifik yang dapat dipastikan pada mode fallback.",
        "bone_joint": "Tidak ada fraktur/dislokasi yang dapat diklaim tanpa model visual tervalidasi atau review klinisi.",
        "lung_pleura_mediastinum_cardiac": "Untuk CXR: airway, paru, pleura, mediastinum, siluet jantung, diafragma, dan perangkat perlu review model/klinisi.",
        "abdomen": "Untuk abdomen: pola gas usus, udara bebas, dan opasitas perlu korelasi klinis.",
        "device_foreign_body": "Perangkat/foreign body tidak dinilai pasti pada mode fallback.",
        "abnormality_list": ["Tidak ada abnormalitas spesifik yang diklaim oleh fallback."],
        "positive_findings": [],
        "negative_important_findings": ["Tidak ada finding negatif penting yang dapat dipastikan otomatis pada mode fallback."],
        "differential_diagnosis": ["Tidak cukup bukti visual untuk DDx spesifik."],
        "final_impression": "Draf kesan non-diagnostik: tidak ada temuan spesifik yang dikonfirmasi AI; perlu verifikasi radiolog/dokter.",
        "confidence": min(0.45, quality.score),
        "limitation": limitation,
    }
    if _is_chest_region(body_region):
        base["alignment_anatomy"] = (
            "Checklist CXR ABCDEF diterapkan sebagai kerangka pikir: airway, breathing/lungs/pleura, "
            "cardiac/mediastinum, diaphragm, everything else/devices/bones, dan failure/edema."
        )
        base["lung_pleura_mediastinum_cardiac"] = (
            "Mode fallback tidak dapat memastikan temuan CXR; laporan harus menilai kualitas/proyeksi, "
            "trakea/hila, kedua paru per zona termasuk apeks, pleura/costophrenic angles, siluet jantung, "
            "mediastinum, diafragma, tulang, jaringan lunak, dan perangkat sebelum membuat kesan."
        )
        base["negative_important_findings"] = [
            "Fallback tidak dapat memastikan pneumotoraks, efusi pleura, konsolidasi, edema, kardiomegali, atau posisi perangkat."
        ]
    elif _is_orthopedic_region(body_region):
        base["adequacy"] = (
            f"Kualitas gambar {quality.exposure}; skor kualitas perkiraan {quality.score:.2f}. "
            "Untuk ortopedi, kecukupan ideal mencakup minimal dua proyeksi ortogonal bila tersedia."
        )
        base["alignment_anatomy"] = (
            "Checklist ortopedi ABCs diterapkan sebagai kerangka pikir: adequacy/alignment, bones, "
            "cartilage/joint spaces, dan soft tissues."
        )
        base["bone_joint"] = (
            "Mode fallback tidak dapat mengklaim fraktur/dislokasi; bila dicurigai, laporan harus menyebut sisi, "
            "tulang, lokasi proksimal/mid/distal, keterlibatan intra-artikular, pola garis fraktur, displacement/apposition, "
            "angulasi, shortening/distraction, kominutif, dan hubungan sendi."
        )
        base["soft_tissue"] = (
            "Untuk ortopedi, jaringan lunak perlu dinilai untuk swelling, efusi/fat-pad sign, gas, benda asing, "
            "atau tanda tidak langsung fraktur okulta."
        )
        base["negative_important_findings"] = [
            "Fallback tidak dapat memastikan fraktur, dislokasi, keterlibatan intra-artikular, atau cedera jaringan lunak."
        ]
    elif _is_abdomen_region(body_region):
        base["adequacy"] = (
            f"Kualitas gambar {quality.exposure}; skor kualitas perkiraan {quality.score:.2f}. "
            "Untuk abdomen, kecukupan ideal menilai cakupan diafragma sampai pelvis bila relevan."
        )
        base["alignment_anatomy"] = (
            "Checklist abdomen polos diterapkan sebagai kerangka pikir: proyeksi/kualitas, pola gas usus, "
            "udara bebas, kalsifikasi/opasitas, tulang, soft tissue, dan perangkat."
        )
        base["abdomen"] = (
            "Mode fallback tidak dapat memastikan temuan abdomen; laporan harus menilai pola gas usus, "
            "dilatasi usus, air-fluid levels bila ada proyeksi tegak/decubitus, udara bebas, kalsifikasi, "
            "opasitas/massa, tulang, jaringan lunak, dan perangkat sebelum membuat kesan."
        )
        base["negative_important_findings"] = [
            "Fallback tidak dapat memastikan obstruksi, ileus, pneumoperitoneum, batu radioopak, atau posisi perangkat."
        ]
    return SystematicReading(**base)


def _result_card_summary(result_cards: list[ResultCard]) -> str:
    if not result_cards:
        return "Belum ada result card terstruktur."
    lines = []
    for card in result_cards:
        score = card.probability if card.probability is not None else card.confidence
        lines.append(f"{card.finding} ({card.status}, {score:.2f}): {card.candidate_diagnosis}.")
    return " ".join(lines)


def _short_text(text: str, limit: int = 1200) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[:limit].rstrip() + ("..." if len(cleaned) > limit else "")


def _cxr_reference_prior_text() -> str:
    return " ".join(f"- {item}" for item in CXR_REFERENCE_PRIORS)


def _reference_prior_text(body_region: str) -> str:
    if _is_chest_region(body_region):
        return _cxr_reference_prior_text()
    return (
        "- Plain radiographs are projectional studies; report visible objective signs and avoid overcalling findings hidden by overlap. "
        "- Preserve laterality, anatomic location, projection/view, and technical limitations. "
        "- Do not infer clinical facts such as open fracture, neurovascular status, fever, trauma mechanism, or laboratory diagnosis from the image alone."
    )


def _primary_observation(reading: SystematicReading) -> str:
    if _is_chest_region(reading.body_region):
        return _short_text(reading.lung_pleura_mediastinum_cardiac, 1200)
    if _is_orthopedic_region(reading.body_region):
        return _short_text(" ".join([reading.alignment_anatomy, reading.bone_joint, reading.soft_tissue]), 1200)
    if _is_abdomen_region(reading.body_region):
        return _short_text(reading.abdomen, 1200)
    return _short_text(" ".join([reading.alignment_anatomy, reading.bone_joint, reading.soft_tissue, reading.abdomen]), 1200)


def _ollama_vision_prompt(custom_prompt: str = "", body_region: str = "Unknown/general X-ray") -> str:
    extra = f"\nAdditional user context: {custom_prompt}" if custom_prompt else ""
    return (
        "Review this X-ray/radiograph as a cautious X-ray research assistant. "
        f"Estimated body-region template: {body_region}. "
        f"Before giving findings or impression, apply this systematic review checklist: {_systematic_review_text(body_region)} "
        f"Use this professional reporting style: {_professional_reporting_text()} "
        "If it is a chest X-ray, use a CXR checklist: projection/quality, right lung, left lung, upper zones/apices, hila/mediastinum, cardiac silhouette, pleura, bones, devices. "
        "If it is an orthopedic/MSK X-ray, use an ABCs orthopedic checklist: adequacy/alignment, bones, cartilage/joint spaces, and soft tissues; describe fractures using standard orthopedic terminology when visible. "
        "If it is an abdomen X-ray, review bowel gas pattern, free air, calcifications/opacities, soft tissues, bones, and devices. "
        "State laterality, anatomic location, zone/level, and extent when visible. Give 2-4 differential considerations only when supported by the image. "
        f"Reference calibration from radiology teaching and reporting standards: {_reference_prior_text(body_region)} "
        "Do not provide a definitive diagnosis. Do not invent clinical history. Keep the response focused on X-ray observations. "
        "Keep the answer concise and structured exactly as: Technique/quality, Findings, Impression, Safety/verification notes. "
        "For chest X-rays, explicitly say whether there is definite, absent, or uncertain cavitation in the Safety/verification notes."
        f"{extra}"
    )


def _vlm_finding_label(text: str) -> str:
    t = text.lower()
    side = "left" if "left" in t else ("right" if "right" in t else "")
    zone = "upper_lung" if any(term in t for term in ["upper", "apex", "apical"]) else "lung"

    def positive_mention(*terms: str) -> bool:
        for term in terms:
            if term not in t:
                continue
            negated = any(
                phrase in t
                for phrase in [
                    f"no {term}",
                    f"no definite {term}",
                    f"no clear {term}",
                    f"no obvious {term}",
                    f"without {term}",
                    f"negative for {term}",
                    f"no evidence of {term}",
                    f"does not show evidence of {term}",
                    f"not show evidence of {term}",
                ]
            ) or bool(re.search(rf"\b(no|no definite|no clear|without|negative for|does not show evidence of|not show evidence of)\b[^,.;:\n]{{0,80}}\b{re.escape(term)}\b", t))
            if not negated:
                return True
        return False

    if positive_mention("cavity", "cavitary", "cavitation", "lucency"):
        prefix = f"possible_{side + '_' if side else ''}{zone}_cavitary_process"
        return prefix
    if positive_mention("consolidation", "opacity", "opacification", "infiltrate", "airspace"):
        return f"possible_{side + '_' if side else ''}{zone}_airspace_opacity"
    if positive_mention("interstitial", "reticular", "fibrosis", "fibrotic", "nodular", "nodularity"):
        return f"possible_{side + '_' if side else ''}{zone}_interstitial_or_fibrotic_change"
    return "ollama_vlm_candidate_observations"


def _json_object_from_text(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _clean_report_field(text: str, limit: int) -> str:
    cleaned = _short_text(text, limit)
    replacements = {
        "Projecti/kualitas": "Proyeksi/kualitas",
        "Projecti": "Proyeksi",
        "lytic": "litik",
        "sclerotic": "sklerotik",
        "tree-in-bud": "temuan CT tree-in-bud",
    }
    for src, dst in replacements.items():
        cleaned = cleaned.replace(src, dst)
    return cleaned


def _fallback_ollama_report(reading: SystematicReading, quality: ImageQuality, report_model: str) -> Report:
    observation = _primary_observation(reading)
    return Report(
        indication="Belum diisi.",
        findings=(
            f"Kualitas gambar diperkirakan {quality.exposure} (skor {quality.score:.2f}). "
            f"Pada draf pembacaan lokal, temuan utama adalah: {observation}"
        ),
        impression=(
            "Draf non-diagnostik: terdapat kandidat temuan radiograf yang perlu korelasi klinis "
            "dan verifikasi radiolog/dokter."
        ),
        recommendation=(
            "Bandingkan dengan gejala, riwayat, pemeriksaan lab/mikrobiologi bila relevan, "
            "dan pertimbangkan follow-up imaging sesuai keputusan klinisi."
        ),
        watermark=f"AI-assisted draft from local Ollama report model {report_model}, not for standalone clinical diagnosis.",
    )


def build_ollama_report(
    case_id: str,
    reading: SystematicReading,
    quality: ImageQuality,
    result_cards: list[ResultCard],
    report_model: str,
    base_url: str,
) -> Report:
    compact_cards = [
        {
            "finding": card.finding,
            "status": card.status,
            "confidence": round(card.confidence, 2),
            "candidate": card.candidate_diagnosis,
            "uncertainty": card.uncertainty_reason,
        }
        for card in result_cards[:4]
    ]
    observation = _primary_observation(reading)
    prompt = (
        "Buat draf laporan radiografi/X-ray bahasa Indonesia dari konteks berikut. "
        "Jawab JSON saja tanpa markdown dengan key: findings, impression, recommendation. "
        "Ikuti struktur laporan radiologi profesional: indikasi tidak diinvent, teknik/proyeksi bila tersedia, temuan objektif, kesan terprioritaskan, dan rekomendasi hanya bila perlu. "
        f"Sebelum menyusun temuan/kesan, gunakan checklist sistematis untuk area ini: {_systematic_review_text(reading.body_region)} "
        f"Prinsip pelaporan: {_professional_reporting_text()} "
        "findings berisi observasi objektif singkat, bukan rekomendasi. "
        "impression harus non-diagnostik dan memakai kata kandidat/kemungkinan bila perlu. "
        "recommendation harus menyebut verifikasi radiolog/dokter. "
        "Jangan ulang teks yang sama, jangan invent riwayat klinis, jangan diagnosis definitif.\n"
        "Gunakan istilah Indonesia rapi seperti Proyeksi/kualitas, opasitas, konsolidasi, kavitas, ileus, obstruksi, litik, sklerotik, dislokasi, subluksasi, fraktur, displacement, dan angulasi sesuai area pemeriksaan. "
        "Untuk foto toraks polos, jangan memakai atau menyebut tree-in-bud; itu pola CT. "
        "Untuk foto toraks polos, jangan menyimpulkan TB aktif lebih rendah hanya karena tidak ada tree-in-bud. "
        "Untuk foto toraks polos, jika tidak ada kavitas jelas, tulis 'tidak tampak kavitas definitif' dan tetap nyatakan opasitas X-ray bersifat tidak spesifik. "
        "Untuk X-ray ortopedi, jika fraktur terlihat, deskripsikan sisi, tulang, lokasi, intra-artikular/tidak, pola garis fraktur, displacement/apposition, angulasi, kominutif, dan hubungan sendi; jangan infer open/closed atau status neurovaskular. "
        "Untuk X-ray abdomen, bedakan pola gas usus, dilatasi, udara bebas, kalsifikasi/opasitas, tulang, soft tissue, dan perangkat bila terlihat. "
        "Jangan menyarankan CT sebagai langkah otomatis; tulis follow-up imaging hanya bila sesuai keputusan klinisi.\n"
        f"Kalibrasi referensi: {_reference_prior_text(reading.body_region)}\n"
        f"Case ID: {case_id}\n"
        f"Quality: {quality.model_dump(mode='json')}\n"
        f"Body region: {reading.body_region}\n"
        f"Primary X-ray observation: {observation}\n"
        f"Result cards: {compact_cards}\n"
        f"Differential considerations: {reading.differential_diagnosis[:4]}"
    )
    content = ollama_chat([{"role": "user", "content": prompt}], report_model, base_url)
    parsed = _json_object_from_text(content)
    findings = _clean_report_field(str(parsed.get("findings") or ""), 1200)
    impression = _clean_report_field(str(parsed.get("impression") or ""), 700)
    recommendation = _clean_report_field(str(parsed.get("recommendation") or ""), 500)
    if not findings or not impression:
        return _fallback_ollama_report(reading, quality, report_model)
    return Report(
        indication="Belum diisi.",
        findings=findings,
        impression=impression,
        recommendation=recommendation or "Korelasikan klinis dan verifikasi oleh radiolog/dokter.",
        watermark=f"AI-assisted draft from local Ollama report model {report_model}, not for standalone clinical diagnosis.",
    )


def build_report(case_id: str, reading: SystematicReading, quality: ImageQuality, result_cards: list[ResultCard] | None = None, language: str = "id") -> Report:
    card_summary = _result_card_summary(result_cards or [])
    if language == "en":
        return Report(
            language="en",
            indication="Not provided.",
            technique="Conventional radiograph; projection details follow available metadata and reviewer input.",
            comparison="Unavailable.",
            findings=(
                f"Image quality is estimated as {quality.exposure} (score {quality.score:.2f}). "
                f"Body region template: {reading.body_region}. Result cards: {card_summary}"
            ),
            impression="AI-assisted non-diagnostic draft based on reviewable result cards; no finding is confirmed without qualified image review.",
            recommendation="Correlate clinically and verify by a qualified radiologist/physician.",
        )
    return Report(
        indication="Belum diisi.",
        findings=(
            f"Identitas kasus: {case_id}. Kualitas gambar diperkirakan {quality.exposure} "
            f"(skor {quality.score:.2f}). Template area: {reading.body_region}. "
            f"Ringkasan result cards: {card_summary}"
        ),
        impression=f"Draf berbantuan AI untuk review manusia: {reading.final_impression}",
        recommendation="Korelasikan dengan kondisi klinis, riwayat, dan pemeriksaan penunjang. Gunakan review radiolog/dokter sebagai acuan.",
    )


async def run_analysis(
    case_id: str,
    image: dict[str, Any],
    custom_prompt: str = "",
    backend: str = "demo",
    runtime_snapshot: dict[str, Any] | None = None,
    language: str = "id",
    anatomy_profile_override: str = "",
) -> dict[str, Any]:
    quality = quality_from_image(image.get("stored_path"))
    anatomy_route_data = resolve_profile_model(
        route_study(image.get("metadata", {}), image.get("filename"), custom_prompt, anatomy_profile_override),
        runtime_snapshot,
    )
    anatomy_route = AnatomyRoute(**anatomy_route_data)
    body_region = anatomy_route.body_region
    reading = systematic_template(body_region, quality, custom_prompt)
    if anatomy_route.view != "unknown":
        reading.view_projection = f"Proyeksi/view terdeteksi: {anatomy_route.view}; wajib dikonfirmasi reviewer terhadap gambar sumber."

    findings = [
        Finding(
            label="fallback_no_confirmed_abnormality",
            description="Fallback hanya memberi struktur pembacaan; tidak mengklaim diagnosis.",
            confidence=reading.confidence,
            status="uncertain",
            evidence=["Aktifkan VLM/classifier/MedRAX tools untuk probabilitas patologi."],
        )
    ]
    classifier_result: dict[str, Any] | None = None
    vision_result: dict[str, Any] | None = None
    localization_result: dict[str, Any] | None = None
    classification_model = str((runtime_snapshot or {}).get("classification_model") or "")
    if is_torchxrayvision_model(classification_model):
        if anatomy_route.profile_id != "chest":
            classifier_result = {
                "status": "skipped",
                "model": classification_model,
                "detail": f"Skipped: {classification_model} supports chest X-ray classification, not {anatomy_route.profile_label}.",
                "warnings": [f"Chest classifier was not run on {anatomy_route.profile_label}."],
            }
        else:
            classifier_result = run_torchxrayvision_classifier(image.get("stored_path"), classification_model)
        if classifier_result.get("status") == "ok":
            parsed_findings: list[Finding] = []
            for item in _list_of_dicts(classifier_result.get("findings")):
                try:
                    parsed_findings.append(Finding(**item))
                except Exception:
                    continue
            if parsed_findings:
                findings = parsed_findings
            else:
                classifier_result["status"] = "failed"
                classifier_result["detail"] = str(classifier_result.get("detail") or "Classifier returned no valid finding records.")
                classifier_result["warnings"] = [*_string_list(classifier_result.get("warnings")), "Classifier output was ignored because it contained no valid finding records."]
        if classifier_result.get("status") == "ok":
            reading.positive_findings = [item.label for item in findings if item.status == "positive"]
            reading.abnormality_list = [item.label for item in findings if item.status in {"positive", "uncertain"}]
            reading.final_impression = (
                "Draf non-diagnostik: classifier lokal menghasilkan sinyal riset terstruktur. "
                "Probabilitas belum dikalibrasi untuk dataset/protokol lokal dan wajib diverifikasi radiolog/dokter."
            )
    if backend == "ollama" and image.get("stored_path"):
        vision_model = anatomy_route.selected_model
        if vision_model and vision_model not in {"disabled", "demo-vlm"}:
            try:
                ollama_base_url = str((runtime_snapshot or {}).get("ollama_base_url") or "")
                require_allowed_endpoint(ollama_base_url, bool((runtime_snapshot or {}).get("allow_cloud", False)))
                content = ollama_vision(
                    image["stored_path"],
                    _ollama_vision_prompt(custom_prompt, body_region),
                    vision_model,
                    ollama_base_url,
                )
                if content.strip():
                    summary = _short_text(content)
                    vision_result = {"status": "ok", "model": vision_model, "content": content}
                    findings = [
                        Finding(
                            label=_vlm_finding_label(summary),
                            description=summary,
                            confidence=min(0.62, max(0.35, quality.score)),
                            status="uncertain",
                            evidence=["Ollama VLM image review; unvalidated local runtime output."],
                        )
                    ]
                    if _is_chest_region(body_region):
                        reading.lung_pleura_mediastinum_cardiac = summary
                    elif _is_orthopedic_region(body_region):
                        reading.bone_joint = summary
                        reading.alignment_anatomy = "Ollama VLM candidate MSK observations; verify alignment and joint congruity on the source image."
                    elif _is_abdomen_region(body_region):
                        reading.abdomen = summary
                    else:
                        reading.alignment_anatomy = summary
                    reading.abnormality_list = ["Ollama VLM candidate observations; verify on source image."]
                    reading.positive_findings = []
                    reading.differential_diagnosis = ["Candidate VLM observations require radiologist verification."]
                    reading.final_impression = (
                        "Draf non-diagnostik berbasis Ollama VLM: "
                        f"{summary} Wajib diverifikasi radiolog/dokter dan tidak boleh dipakai sebagai diagnosis final mandiri."
                    )
            except Exception as exc:
                vision_result = {"status": "failed", "model": vision_model, "detail": str(exc)}

    grounding_model = str((runtime_snapshot or {}).get("grounding_model") or "disabled").strip()
    if grounding_model and grounding_model not in {"disabled", "demo-grounding"}:
        if anatomy_route.profile_id != "msk":
            localization_result = {
                "status": "skipped",
                "model": grounding_model,
                "detail": f"MSK fracture localization is not supported for {anatomy_route.profile_label}.",
                "detections": [],
                "warnings": [f"MSK detector was not run on {anatomy_route.profile_label}."],
            }
        elif not grounding_model.startswith("local:"):
            localization_result = {
                "status": "skipped",
                "model": grounding_model,
                "detail": "Phase 3 localization accepts only a human-reviewed local artifact ID.",
                "detections": [],
                "warnings": ["Grounding model was not run because it is not a reviewed local artifact."],
            }
        else:
            localization_result = run_msk_fracture_detector(
                image.get("stored_path"),
                grounding_model,
                cpu_only=bool((runtime_snapshot or {}).get("cpu_only", True)),
                threshold=float((runtime_snapshot or {}).get("localization_confidence_threshold", 0.25)),
            )

    localization_detections = [
        item for item in _list_of_dicts((localization_result or {}).get("detections"))
        if isinstance(item.get("coordinate"), dict)
    ]
    if localization_result and localization_result.get("status") == "ok" and (localization_result.get("detections") and not localization_detections):
        localization_result["status"] = "failed"
        localization_result["detail"] = str(localization_result.get("detail") or "Detector returned no valid detection records.")
        localization_result["warnings"] = [*_string_list(localization_result.get("warnings")), "Detector output was ignored because it contained no valid coordinate records."]
    if localization_result and localization_result.get("status") == "ok" and localization_detections:
        localization_finding = Finding(
            label="candidate_fracture_localization",
            description=f"Detector lokal menghasilkan {len(localization_detections)} kandidat lokasi fraktur untuk review manusia.",
            confidence=max(float(item.get("confidence", 0) or 0) for item in localization_detections),
            status="uncertain",
            evidence=[
                f"Bounding boxes returned by reviewed local detector {grounding_model}.",
                "Localization has not been established as clinical performance and requires box-level validation.",
            ],
        )
        findings = [localization_finding] if all(item.label.startswith("fallback_") for item in findings) else [*findings, localization_finding]
        reading.positive_findings = [*reading.positive_findings, "Candidate fracture localization; unconfirmed."]
        reading.abnormality_list = [*reading.abnormality_list, "Candidate fracture box(es) from local detector."]
        reading.final_impression = (
            "Draf non-diagnostik: detector lokal menandai kandidat lokasi fraktur. "
            "Konfirmasi temuan, anatomi, dan geometri kotak pada gambar sumber oleh radiolog/dokter diperlukan."
        )
    annotations = []
    width = image.get("width") or (localization_result or {}).get("original_width") or 0
    height = image.get("height") or (localization_result or {}).get("original_height") or 0
    if width and height:
        image_metadata = image.get("metadata") if isinstance(image.get("metadata"), dict) else {}
        source_image_id = str(image.get("source_image_id") or image_metadata.get("SOPInstanceUID") or image.get("filename") or f"{case_id}:0")
        source_image_index = int(image.get("source_image_index") or 0)
        source_view = str(image.get("source_view") or image_metadata.get("ViewPosition") or image_metadata.get("view") or "")
        source_series_id = str(image.get("source_series_id") or image_metadata.get("SeriesInstanceUID") or "")
        for detection in localization_detections:
            detection_coordinate = detection.get("coordinate") if isinstance(detection.get("coordinate"), dict) else {}
            coordinate = Coordinate(type="grounding_box", coordinate_space="original_image", **detection_coordinate)
            explanation = (
                f"Unvalidated candidate fracture box from {grounding_model}; detector label "
                f"'{detection.get('model_label', 'fracture')}'. Requires qualified human confirmation."
            )
            annotations.append(Annotation(
                label="candidate fracture localization",
                confidence=float(detection.get("confidence", 0)),
                source=AnnotationSource.MODEL_COORDINATE,
                source_model=grounding_model,
                source_model_version=Path(str((localization_result or {}).get("weights") or "")).name,
                coordinate=coordinate,
                original_coordinate=coordinate.model_copy(deep=True),
                original_state=AnnotationOriginalState(
                    label="candidate fracture localization",
                    confidence=float(detection.get("confidence", 0)),
                    coordinate=coordinate.model_copy(deep=True),
                    explanation=explanation,
                ),
                explanation=explanation,
                source_image_id=source_image_id,
                source_image_index=source_image_index,
                source_view=source_view,
                source_series_id=source_series_id,
                transform_metadata=AnnotationTransformMetadata(
                    source_space="original_image",
                    display_space="original_image",
                    original_width=width,
                    original_height=height,
                    model_input_width=(localization_result or {}).get("model_input_width"),
                    model_input_height=(localization_result or {}).get("model_input_height"),
                    note="Detector xyxy output was restored and validated in original-image pixel coordinates.",
                ),
            ))
        if not annotations:
            fallback_coordinate = Coordinate(x=width * 0.15, y=height * 0.15, width=width * 0.7, height=height * 0.7, coordinate_space="original_image")
            annotations.append(Annotation(
                label="demo global review region",
                confidence=0.2,
                source=AnnotationSource.FALLBACK_HEURISTIC,
                coordinate=fallback_coordinate,
                original_coordinate=fallback_coordinate.model_copy(deep=True),
                original_state=AnnotationOriginalState(
                    label="demo global review region",
                    confidence=0.2,
                    coordinate=fallback_coordinate.model_copy(deep=True),
                    explanation="Area pandang umum fallback, bukan lokasi patologi.",
                ),
                explanation="Area pandang umum fallback, bukan lokasi patologi.",
                source_image_id=source_image_id,
                source_image_index=source_image_index,
                source_view=source_view,
                source_series_id=source_series_id,
                transform_metadata=AnnotationTransformMetadata(
                    source_space="original_image",
                    display_space="original_image",
                    original_width=width,
                    original_height=height,
                    note="Fallback review region uses original image coordinates and no model localization transform.",
                ),
            ))

    context = {"case_id": case_id, "image": image, "custom_prompt": custom_prompt}
    tool_results = await AgentOrchestrator(demo_medrax_tools()).run(context)
    trace = [
        ModelTrace(stage=item["task_type"], backend=backend, model=item["tool"], status=item["status"], detail=item["message"])
        for item in tool_results
    ]
    trace.insert(0, ModelTrace(
        stage="anatomy_routing",
        backend="local-router",
        model=anatomy_route.model_slot,
        status="ok" if anatomy_route.profile_id != "general" else "fallback",
        detail=(
            f"profile={anatomy_route.profile_id}; anatomy={anatomy_route.anatomy}; laterality={anatomy_route.laterality}; "
            f"view={anatomy_route.view}; source={anatomy_route.source}; confidence={anatomy_route.confidence:.2f}; "
            f"model={anatomy_route.selected_model}; support={anatomy_route.support_status}"
        ),
    ))
    trace.insert(0, ModelTrace(stage="custom_prompt", backend=backend, model="pipeline", status="ok" if custom_prompt else "skipped", detail=custom_prompt[:300]))
    if vision_result:
        trace.append(
            ModelTrace(
                stage="vision_language",
                backend=backend,
                model=str(vision_result.get("model") or ""),
                status=vision_result.get("status", "failed"),
                detail=str(vision_result.get("content") or vision_result.get("detail") or "")[:1200],
            )
        )
    if classifier_result:
        trace.append(
            ModelTrace(
                stage="anatomy_classification",
                backend=backend,
                model=str(classifier_result.get("model") or classification_model),
                status=classifier_result.get("status", "failed"),
                detail=str(classifier_result.get("detail", ""))[:600],
            )
        )
    if localization_result:
        trace.append(
            ModelTrace(
                stage="msk_fracture_localization",
                backend="ultralytics-local",
                model=str(localization_result.get("model") or grounding_model),
                status=localization_result.get("status", "failed"),
                detail=str(localization_result.get("detail", ""))[:600],
            )
        )

    result_cards = compose_result_cards(findings, annotations, trace, quality)
    active_metadata = image.get("metadata") if isinstance(image.get("metadata"), dict) else {}
    active_source_image_id = str(image.get("source_image_id") or active_metadata.get("SOPInstanceUID") or image.get("filename") or f"{case_id}:0")
    active_source_series_id = str(image.get("source_series_id") or active_metadata.get("SeriesInstanceUID") or "")
    active_source_view = str(image.get("source_view") or active_metadata.get("ViewPosition") or "")
    for card in result_cards:
        card.source_image_ids = [active_source_image_id]
        card.source_series_ids = [active_source_series_id] if active_source_series_id else []
        card.source_views = [active_source_view] if active_source_view else []
    linked_card_ids = {ref: card.id for card in result_cards for ref in card.annotation_refs}
    for annotation in annotations:
        if annotation.id in linked_card_ids:
            annotation.linked_result_card_ids = [linked_card_ids[annotation.id]]

    report_model = str((runtime_snapshot or {}).get("report_model") or "").strip()
    report_language = "en" if language == "en" else "id"
    report = build_report(case_id, reading, quality, result_cards, language=report_language)
    if report_language == "id" and backend == "ollama" and report_model and report_model not in {"disabled", "demo-report-generator"}:
        try:
            ollama_base_url = str((runtime_snapshot or {}).get("ollama_base_url") or "")
            require_allowed_endpoint(ollama_base_url, bool((runtime_snapshot or {}).get("allow_cloud", False)))
            report = build_ollama_report(
                case_id,
                reading,
                quality,
                result_cards,
                report_model,
                ollama_base_url,
            )
            trace.append(ModelTrace(stage="report_generation", backend=backend, model=report_model, status="ok", detail="Local Ollama report draft generated."))
        except Exception as exc:
            trace.append(ModelTrace(stage="report_generation", backend=backend, model=report_model, status="failed", detail=str(exc)[:600]))

    result = AnalysisResult(
        case_id=case_id,
        input=AnalysisInput(
            image_path=image.get("stored_path"),
            filename=image.get("filename"),
            format=image.get("format"),
            width=image.get("width"),
            height=image.get("height"),
            metadata=image.get("metadata", {}),
            custom_prompt=custom_prompt,
            source_image_id=str(image.get("source_image_id") or ""),
            source_image_index=int(image.get("source_image_index") or 0),
            source_series_id=str(image.get("source_series_id") or ""),
            source_view=str(image.get("source_view") or ""),
        ),
        image_quality=quality,
        findings=findings,
        annotations=annotations,
        result_cards=result_cards,
        differential_diagnosis=build_differential_assistance(
            [card.model_dump(mode="json") for card in result_cards], report.model_dump(mode="json")
        ),
        anatomy_route=anatomy_route,
        systematic_reading=reading,
        report=report,
        model_trace=trace,
        input_hashes=image.get("hashes") or {},
        runtime_snapshot=runtime_snapshot or {"primary_backend": backend},
    warnings=[
            "Aplikasi hanya untuk riset, edukasi, dan prototyping; bukan alat diagnosis klinis resmi.",
            (
                "Ollama VLM aktif; output adalah kandidat observasi tidak tervalidasi dan wajib diverifikasi radiolog/dokter."
                if vision_result and vision_result.get("status") == "ok"
                else "Mode demo/fallback aktif sampai model runtime dikonfigurasi."
            ),
        ]
        + ([f"Ollama VLM gagal: {vision_result.get('detail')}"] if vision_result and vision_result.get("status") == "failed" else [])
        + (_string_list(classifier_result.get("warnings")) if classifier_result else [])
        + (_string_list(localization_result.get("warnings")) if localization_result else [])
        + anatomy_route.warnings,
    )
    return OutputNormalizer().normalize(result)
