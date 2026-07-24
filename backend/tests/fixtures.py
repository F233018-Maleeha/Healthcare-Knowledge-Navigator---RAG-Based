from datetime import date

from app.models.schemas import AuthorityTier, SourceDocument

SAMPLE_DOCS = [
    SourceDocument(
        doc_id="doc-01",
        title="Hypertension Management Overview",
        source="Synthetic guideline summary",
        specialty=["cardiology"],
        authority_tier=AuthorityTier.GUIDELINE_OR_META_ANALYSIS,
        evidence_grade="Grade A",
        publication_date=date(2023, 5, 1),
        full_text=(
            "Background\n"
            "Hypertension is a leading modifiable risk factor for cardiovascular disease.\n"
            "Recommendation\n"
            "For most adults, a blood pressure target below 130/80 mmHg is reasonable, "
            "especially in patients with diabetes, chronic kidney disease, or established "
            "cardiovascular disease. First-line pharmacologic classes include ACE inhibitors, "
            "ARBs, calcium channel blockers, and thiazide-type diuretics. In patients with "
            "diabetes and hypertension, an ACE inhibitor or ARB is generally preferred given "
            "renal-protective effects."
        ),
    ),
    SourceDocument(
        doc_id="doc-03",
        title="Atrial Fibrillation Anticoagulation Overview",
        source="Synthetic guideline summary",
        specialty=["cardiology"],
        authority_tier=AuthorityTier.GUIDELINE_OR_META_ANALYSIS,
        evidence_grade="Grade A",
        publication_date=date(2023, 8, 1),
        full_text=(
            "Recommendation\n"
            "Anticoagulation decisions in non-valvular atrial fibrillation are guided by the "
            "CHA2DS2-VASc score. A score of 2 or more in men (3 or more in women) generally "
            "warrants oral anticoagulation. Direct oral anticoagulants are preferred over "
            "warfarin for most eligible patients.\n"
            "Contraindications\n"
            "Warfarin remains preferred in patients with moderate-to-severe mitral stenosis "
            "or a mechanical heart valve, where DOACs are not validated."
        ),
    ),
    SourceDocument(
        doc_id="doc-05",
        title="STEMI Reperfusion Timing",
        source="Synthetic guideline summary",
        specialty=["cardiology"],
        authority_tier=AuthorityTier.SYSTEMATIC_REVIEW,
        evidence_grade="Grade B",
        publication_date=date(2021, 9, 1),
        full_text=(
            "Recommendation\n"
            "For ST-elevation myocardial infarction, primary percutaneous coronary "
            "intervention is preferred over fibrinolysis when it can be performed promptly. "
            "The benchmark is a first-medical-contact-to-device time of 90 minutes or less "
            "at a PCI-capable facility, or 120 minutes when transfer is required."
        ),
    ),
]
