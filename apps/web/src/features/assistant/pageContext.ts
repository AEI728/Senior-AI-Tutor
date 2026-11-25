export function readPageContext(pathname: string) {
  const page = pathname.startsWith("/lessons") ? "lesson"
    : pathname.startsWith("/skills") ? "skills"
    : ["/share", "/community"].includes(pathname) ? "community"
    : pathname.startsWith("/recommend/") ? "recommendation"
    : pathname.startsWith("/practice") ? "practice" : "home";
  let work: HTMLElement | null = null;
  if (page === "community" || page === "recommendation") {
    work = document.querySelector<HTMLElement>(".work-fullscreen[data-work-id], .recommendation-only[data-work-id]");
    if (!work) {
      const cards = [...document.querySelectorAll<HTMLElement>(".feed-list .feed-card[data-work-id]")];
      const visible = cards.filter(card => {
        const box = card.getBoundingClientRect();
        const height = Math.min(box.bottom, innerHeight) - Math.max(box.top, 0);
        return box.height > 0 && height / box.height > 0.6 && box.right > 0 && box.left < innerWidth;
      });
      if (visible.length === 1) work = visible[0];
    }
  }
  return {
    page,
    focused_skill_id: pathname.startsWith("/skills/") ? decodeURIComponent(pathname.split("/")[2]) : null,
    course_id: page === "lesson" ? decodeURIComponent(pathname.split("/")[2]) : null,
    focused_work_id: work?.dataset.workId || null,
  };
}
