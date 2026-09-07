interface Props {
  rows: unknown;
  capCols?: number;
  capRows?: number;
  heat?: boolean;
}

function asTable(rows: unknown): {
  cols: string[];
  body: string[][];
  nums: (number | null)[][];
  maxs: (number | null)[];
  subs: Record<string, string>[];
} | null {
  let list = rows;
  if (!Array.isArray(list) && typeof list === "object" && list !== null) {
    const first = Object.values(list as Record<string, unknown>).find((v) =>
      Array.isArray(v),
    );
    if (!first) return null;
    list = first;
  }
  if (!Array.isArray(list) || !list.length) return null;
  const first = (list as unknown[])[0] as Record<string, unknown>;
  if (typeof first !== "object" || first === null) return null;
  const cols = Object.keys(first).slice(0, 8);
  const recs = (list as Record<string, unknown>[]).slice(0, 10);
  const body = recs.map((r) =>
    cols.map((c) => {
      const v = r[c];
      if (v === null || v === undefined) return "";
      if (typeof v === "object") return JSON.stringify(v).slice(0, 60);
      return String(v).slice(0, 60);
    }),
  );
  const subs = recs.map((r) => {
    const out: Record<string, string> = {};
    if (typeof r.PLAYER === "string") {
      const bits = [];
      if (typeof r.TEAM === "string") bits.push(r.TEAM);
      if (typeof r.RANK === "number") bits.push(`#${r.RANK}`);
      if (bits.length) out.PLAYER = bits.join(" · ");
    }
    return out;
  });
  const nums = recs.map((r) =>
    cols.map((c) => {
      const v = r[c];
      return typeof v === "number" ? v : null;
    }),
  );
  const maxs = cols.map((_, j) => {
    const vals = nums.map((row) => row[j]).filter((v) => v !== null) as number[];
    if (!vals.length) return null;
    const m = Math.max(...vals.map((v) => Math.abs(v)));
    return m > 0 ? m : null;
  });
  return { cols, body, nums, maxs, subs };
}

export default function DataTable({ rows, capCols = 8, capRows = 10, heat = false }: Props) {
  const t = asTable(rows);
  if (!t) return null;
  void capCols;
  void capRows;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
        <thead>
          <tr>
            {t.cols.map((c) => (
              <th
                key={c}
                style={{
                  textAlign: "left",
                  borderBottom: "1px solid #e8e6e5",
                  padding: "4px 8px",
                  color: "#78716c",
                  fontWeight: 500,
                }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {t.body.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => {
                const v = t.nums[i][j];
                const m = t.maxs[j];
                const bg =
                  heat && v !== null && m !== null
                    ? `rgba(59, 166, 241, ${(0.04 + 0.22 * (Math.abs(v) / m)).toFixed(3)})`
                    : undefined;
                return (
                  <td
                    key={j}
                    style={{
                      borderBottom: "1px solid #e8e6e5",
                      padding: "4px 8px",
                      background: bg,
                    }}
                  >
                    {cell}
                    {t.subs[i][t.cols[j]] && (
                      <div style={{ fontSize: 10, color: "#a8a29e" }}>
                        {t.subs[i][t.cols[j]]}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
