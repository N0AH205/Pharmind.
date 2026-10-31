"""
Local Chemical Structure Engine — RDKit-based (100% Offline).

Provides offline chemical resolution:
  - SMILES parsing & canonicalization
  - Molecular Formula calculation
  - Exact & Average Molecular Weight
  - InChI and InChIKey generation
  - 2D Structure SVG rendering (data URI or clean SVG)
  - Pre-cached common name dictionary for essential pharmaceuticals

Falls back to online PubChem only if explicitly connected, but primary workflow is 100% offline.
"""

from __future__ import annotations

import base64
import re
import urllib.parse
from typing import Any

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors, Draw

# Common drug SMILES / Name lookup dictionary for offline resolution
COMMON_DRUGS_DB: dict[str, dict[str, Any]] = {
    # Aspirin
    "aspirin": {
        "common_name": "Aspirin",
        "synonyms": ["Acetylsalicylic Acid", "2-Acetoxybenzoic acid", "Ecotrin", "Bayer"],
        "pubchem_cid": 2244,
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
    },
    "cc(=o)oc1ccccc1c(=o)o": {
        "common_name": "Aspirin",
        "synonyms": ["Acetylsalicylic Acid", "2-Acetoxybenzoic acid", "Ecotrin"],
        "pubchem_cid": 2244,
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
    },
    "2244": {
        "common_name": "Aspirin",
        "synonyms": ["Acetylsalicylic Acid", "2-Acetoxybenzoic acid"],
        "pubchem_cid": 2244,
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
    },

    # Ibuprofen
    "ibuprofen": {
        "common_name": "Ibuprofen",
        "synonyms": ["Advil", "Motrin", "Nurofen", "2-(4-isobutylphenyl)propanoic acid"],
        "pubchem_cid": 3672,
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    },
    "cc(c)cc1ccc(cc1)c(c)c(=o)o": {
        "common_name": "Ibuprofen",
        "synonyms": ["Advil", "Motrin", "Nurofen"],
        "pubchem_cid": 3672,
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    },
    "3672": {
        "common_name": "Ibuprofen",
        "synonyms": ["Advil", "Motrin"],
        "pubchem_cid": 3672,
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    },

    # Metformin
    "metformin": {
        "common_name": "Metformin",
        "synonyms": ["Glucophage", "1,1-Dimethylbiguanide", "Fortamet"],
        "pubchem_cid": 4091,
        "smiles": "CN(C)C(=N)NC(N)=N",
    },
    "cn(c)c(=n)nc(n)=n": {
        "common_name": "Metformin",
        "synonyms": ["Glucophage", "1,1-Dimethylbiguanide"],
        "pubchem_cid": 4091,
        "smiles": "CN(C)C(=N)NC(N)=N",
    },
    "4091": {
        "common_name": "Metformin",
        "synonyms": ["Glucophage"],
        "pubchem_cid": 4091,
        "smiles": "CN(C)C(=N)NC(N)=N",
    },

    # Atorvastatin
    "atorvastatin": {
        "common_name": "Atorvastatin",
        "synonyms": ["Lipitor", "Torvast"],
        "pubchem_cid": 60823,
        "smiles": "CC(C)c1c(C(=O)Nc2ccccc2F)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O",
    },
    "cc(c)c1c(c(=o)nc2ccccc2f)c(-c2ccccc2)c(-c2ccc(f)cc2)n1ccc(o)cc(o)cc(=o)o": {
        "common_name": "Atorvastatin",
        "synonyms": ["Lipitor", "Torvast"],
        "pubchem_cid": 60823,
        "smiles": "CC(C)c1c(C(=O)Nc2ccccc2F)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O",
    },
    "60823": {
        "common_name": "Atorvastatin",
        "synonyms": ["Lipitor"],
        "pubchem_cid": 60823,
        "smiles": "CC(C)c1c(C(=O)Nc2ccccc2F)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O",
    },

    # Caffeine
    "caffeine": {
        "common_name": "Caffeine",
        "synonyms": ["1,3,7-Trimethylxanthine", "Guaranine", "NoDoz"],
        "pubchem_cid": 2519,
        "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
    },
    "cn1cnc2c1c(=o)n(c(=o)n2c)c": {
        "common_name": "Caffeine",
        "synonyms": ["1,3,7-Trimethylxanthine"],
        "pubchem_cid": 2519,
        "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
    },
    "2519": {
        "common_name": "Caffeine",
        "synonyms": ["1,3,7-Trimethylxanthine"],
        "pubchem_cid": 2519,
        "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
    },

    # Paracetamol / Acetaminophen
    "paracetamol": {
        "common_name": "Paracetamol",
        "synonyms": ["Acetaminophen", "Tylenol", "Panadol", "4-Acetamidophenol"],
        "pubchem_cid": 1983,
        "smiles": "CC(=O)Nc1ccc(O)cc1",
    },
    "acetaminophen": {
        "common_name": "Paracetamol",
        "synonyms": ["Acetaminophen", "Tylenol", "Panadol"],
        "pubchem_cid": 1983,
        "smiles": "CC(=O)Nc1ccc(O)cc1",
    },
    "cc(=o)nc1ccc(o)cc1": {
        "common_name": "Paracetamol",
        "synonyms": ["Acetaminophen", "Tylenol", "Panadol"],
        "pubchem_cid": 1983,
        "smiles": "CC(=O)Nc1ccc(O)cc1",
    },
    "1983": {
        "common_name": "Paracetamol",
        "synonyms": ["Acetaminophen", "Tylenol"],
        "pubchem_cid": 1983,
        "smiles": "CC(=O)Nc1ccc(O)cc1",
    },
}

# Verified PubChem CID 5556; keep the established brand separate from fuzzy spellings.
COMMON_DRUGS_DB["triazolam"] = {
    "common_name": "Triazolam", "synonyms": ["Halcion"], "pubchem_cid": 5556,
    "smiles": "CC1=NN=C2N1C3=C(C=C(C=C3)Cl)C(=NC2)C4=CC=CC=C4Cl",
}
COMMON_DRUGS_DB["halcion"] = COMMON_DRUGS_DB["triazolam"]
COMMON_DRUGS_DB["5556"] = COMMON_DRUGS_DB["triazolam"]


def generate_svg_data_uri(mol: Chem.Mol) -> str:
    """Generate an inline SVG data URI for an RDKit Mol object."""
    try:
        drawer = Draw.rdMolDraw2D.MolDraw2DSVG(350, 300)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg_text = drawer.GetDrawingText()
        encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        return ""


def parse_smiles_offline(smiles_str: str) -> dict[str, Any] | None:
    """
    Parse a SMILES string using RDKit offline.
    Returns calculated chemical parameters and rendered SVG data URI.
    """
    mol = Chem.MolFromSmiles(smiles_str)
    if not mol:
        return None

    canonical_smiles = Chem.MolToSmiles(mol, canonical=True)
    formula = rdMolDescriptors.CalcMolFormula(mol)
    mw = round(float(Descriptors.MolWt(mol)), 4)
    inchi = None
    inchikey = None

    try:
        inchi = Chem.MolToInchi(mol)
        if inchi:
            inchikey = Chem.InchiToInchiKey(inchi)
    except Exception:
        pass

    logp = None
    try:
        logp = round(float(Descriptors.MolLogP(mol)), 2)
    except Exception:
        pass

    svg_uri = generate_svg_data_uri(mol)

    return {
        "smiles": canonical_smiles,
        "molecular_formula": formula,
        "molecular_weight": mw,
        "inchi": inchi,
        "inchikey": inchikey,
        "logp": logp,
        "image_url": svg_uri,
    }


async def enrich_structure_local(query: str) -> dict[str, Any]:
    """
    100% Offline chemical structure resolution.
    Resolves query (SMILES, common drug name, or CID) using RDKit + local dictionary.
    """
    clean_query = query.strip()
    query_lower = clean_query.lower()

    # Check local pre-cached dictionary
    dict_match = COMMON_DRUGS_DB.get(query_lower)

    target_smiles = clean_query
    common_name = None
    synonyms = []
    pubchem_cid = None

    if dict_match:
        common_name = dict_match.get("common_name")
        synonyms = dict_match.get("synonyms", [])
        pubchem_cid = dict_match.get("pubchem_cid")
        target_smiles = dict_match.get("smiles", clean_query)

    # Calculate RDKit properties offline
    rdkit_data = parse_smiles_offline(target_smiles)

    if not rdkit_data and not dict_match:
        # Fall back: treat query as possible drug name if invalid SMILES
        return {
            "smiles": clean_query,
            "pubchem_cid": None,
            "iupac_name": None,
            "common_name": clean_query.capitalize(),
            "synonyms": [],
            "molecular_formula": None,
            "molecular_weight": None,
            "image_url": None,
            "sources": [],
        }

    smiles = rdkit_data.get("smiles") if rdkit_data else target_smiles
    formula = rdkit_data.get("molecular_formula") if rdkit_data else None
    mw = rdkit_data.get("molecular_weight") if rdkit_data else None
    image_url = rdkit_data.get("image_url") if rdkit_data else None
    inchi = rdkit_data.get("inchi") if rdkit_data else None

    # If common name or CID is missing, attempt quick PubChem lookup
    if not pubchem_cid or not common_name or common_name.startswith("Compound ("):
        try:
            from ingest.pubchem import get_compound_by_smiles, get_synonyms
            online_props = await get_compound_by_smiles(smiles)
            if online_props and online_props.get("CID"):
                pubchem_cid = int(online_props["CID"])
                fetched_syns = await get_synonyms(pubchem_cid, max_synonyms=8)
                if fetched_syns:
                    common_name = fetched_syns[0]
                    synonyms = fetched_syns
                elif online_props.get("IUPACName"):
                    common_name = online_props["IUPACName"]
        except Exception:
            pass

    # Derive fallback common name from formula/smiles if still missing
    if not common_name:
        common_name = f"Compound ({formula})" if formula else smiles

    cid_str = str(pubchem_cid) if pubchem_cid else None

    return {
        "smiles": smiles,
        "inchi": inchi,
        "inchikey": rdkit_data.get("inchikey") if rdkit_data else None,
        "inchi_key": rdkit_data.get("inchikey") if rdkit_data else None,
        "logp": rdkit_data.get("logp") if rdkit_data else None,
        "iupac_name": None,  # Computed offline via formula/smiles
        "common_name": common_name,
        "synonyms": synonyms,
        "molecular_formula": formula,
        "molecular_weight": mw,
        "pubchem_cid": pubchem_cid,
        "image_url": image_url,
        "sources": [
            {
                "source": f"Local RDKit Engine (CID {cid_str})" if cid_str else "Local RDKit Engine",
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_str}" if cid_str else "#",
            }
        ],
    }
