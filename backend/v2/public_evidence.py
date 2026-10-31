"""Projection of retained typed evidence for independent domain consumers."""
def public_evidence_table(item):
    return {'tool': item.capability, 'rows': item.rows, 'meta': {'source': item.source, 'source_as_of': item.as_of.isoformat() if item.as_of else None, 'observed_at': item.observed_at.isoformat(), 'season': item.season, 'as_of': item.as_of.isoformat() if item.as_of else None, 'qualification': item.qualification, 'coverage': item.coverage, 'warnings': item.warnings}}
