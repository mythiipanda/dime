def seed_cap_history(con):
    from shared.sources.cap_history import APRON, ROWS

    con.execute(
        "CREATE TABLE IF NOT EXISTS silver_cap_history ("
        "season INTEGER, season_label VARCHAR, salary_cap DOUBLE, "
        "luxury_tax DOUBLE, apron_1 DOUBLE, apron_2 DOUBLE)")
    for end_year, cap_m, tax_m in ROWS:
        if tax_m is None or end_year not in APRON:
            continue
        apron1, apron2 = APRON[end_year]
        con.execute(
            "INSERT INTO silver_cap_history VALUES (?, ?, ?, ?, ?, ?)",
            [end_year, f"{end_year - 1}-{str(end_year)[2:]}",
             cap_m * 1_000_000, tax_m * 1_000_000,
             apron1 * 1_000_000, apron2 * 1_000_000])
