export type SavedThread = {
  id: string;
  title: string;
  when: string;
  preview: string;
  artifacts: number;
};

export const savedThreads: SavedThread[] = [
  {
    id: "sga-luka",
    title: "SGA vs Luka — scoring and efficiency",
    when: "Oct 6, 4:12a",
    preview: "Thirty-game scoring, true shooting, and on/off splits for both guards.",
    artifacts: 3,
  },
  {
    id: "mvp-ladder",
    title: "Jokić MVP case vs the field",
    when: "Oct 5, 11:48p",
    preview: "Rating, trend, and lineup impact for the top six candidates.",
    artifacts: 2,
  },
  {
    id: "okc-closing",
    title: "OKC closing lineups",
    when: "Oct 5, 9:03p",
    preview: "Five-man units by net rating in clutch minutes.",
    artifacts: 1,
  },
  {
    id: "tonight-edges",
    title: "Tonight's slate — where the model disagrees",
    when: "Oct 4, 6:30p",
    preview: "Six games, lines, and the two spots with real separation.",
    artifacts: 2,
  },
  {
    id: "curry-threes",
    title: "Curry threes prop",
    when: "Oct 3, 10:15p",
    preview: "Hit rate over the last 10 against the 4.5 line.",
    artifacts: 1,
  },
  {
    id: "dal-wing",
    title: "Trade: Dallas needs a wing",
    when: "Oct 2, 8:44p",
    preview: "Salary matching and two realistic targets.",
    artifacts: 2,
  },
];
