# M.6 -- incremental update: given new evidence, find only the Intelligence Objects it could
# affect (by topic), rather than recomputing the whole corpus every time. A separate full-rebuild
# mode may exist elsewhere; this module intentionally does only the affected-subset lookup.
def find_affected_objects(new_evidence_topic, objects_by_id):
    """objects_by_id: output of intelligence_object.load_intelligence_objects(). Returns the
    subset of objects whose topic matches the new evidence's topic -- never the whole corpus."""
    return {oid: o for oid, o in objects_by_id.items() if o.get("topic") == new_evidence_topic}


def classify_impact(old_obj, new_obj):
    """Deterministic impact classification comparing two versions of the same object. Never
    fabricated -- derived purely from field-level diffs the caller already made."""
    if old_obj is None:
        return "NEW_GAP_DISCOVERED" if new_obj.get("known_gaps") else "NEW_EVIDENCE_NO_CHANGE"
    if old_obj.get("current_state") != new_obj.get("current_state"):
        return "STATE_CHANGED"
    if len(new_obj.get("counterevidence", [])) > len(old_obj.get("counterevidence", [])):
        return "CLAIM_CONTESTED"
    if len(new_obj.get("uncertainties", [])) > len(old_obj.get("uncertainties", [])):
        return "UNCERTAINTY_INCREASED"
    if len(new_obj.get("uncertainties", [])) < len(old_obj.get("uncertainties", [])):
        return "UNCERTAINTY_REDUCED"
    if len(new_obj.get("known_gaps", [])) < len(old_obj.get("known_gaps", [])):
        return "GAP_CLOSED"
    if len(new_obj.get("known_gaps", [])) > len(old_obj.get("known_gaps", [])):
        return "NEW_GAP_DISCOVERED"
    return "NEW_EVIDENCE_NO_CHANGE"
