import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, friendly } from "../../lib/api";
type Learning = {
  skills: any[];
  library: any[];
  completed: any[];
  progress: any[];
  courses: Record<string, any[]>;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  user: any;
};
const Context = createContext<Learning>(null!);
export function LearningProvider({
  user,
  children,
}: {
  user: any;
  children: ReactNode;
}) {
  const [state, setState] = useState<Omit<Learning, "refresh" | "user">>({
    skills: [],
    library: [],
    completed: [],
    progress: [],
    courses: {},
    loading: true,
    error: "",
  });
  const metadata = useRef<{
    skills: any[];
    courses: Record<string, any[]>;
  } | null>(null);
  const pending = useRef<Promise<void> | null>(null);
  function refresh() {
    if (pending.current) return pending.current;
    pending.current = (async () => {
      try {
        const [library, progress, completed] = await Promise.all([
          api("/library"),
          api("/progress/recent"),
          api("/library/completed"),
        ]);
        if (!metadata.current) {
          const catalog = await api("/catalog/skills");
          const courses = Object.fromEntries(
            await Promise.all(
              catalog.items.map(async (s: any) => [
                s.id,
                (await api("/catalog/skills/" + s.id + "/courses")).items,
              ]),
            ),
          );
          metadata.current = { skills: catalog.items, courses };
        }
        const { skills, courses } = metadata.current;
        setState({
          skills,
          library: library.items,
          completed: completed.items,
          progress: progress.items,
          courses,
          loading: false,
          error: "",
        });
      } catch (e) {
        setState((s) => ({ ...s, loading: false, error: friendly(e) }));
      } finally {
        pending.current = null;
      }
    })();
    return pending.current;
  }
  useEffect(() => {
    void refresh();
    const update = () => void refresh();
    window.addEventListener("learning-changed", update);
    return () => window.removeEventListener("learning-changed", update);
  }, []);
  return (
    <Context.Provider value={{ ...state, refresh, user }}>
      {children}
    </Context.Provider>
  );
}
export const useLearning = () => useContext(Context);
