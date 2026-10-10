import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { sanitizeReply } from "../sanitize";

const components: Components = {
  p: (props) => <p className="font-body-md text-body-md [&:not(:first-child)]:mt-2" {...props} />,
  h1: (props) => <h3 className="font-headline-sm text-headline-sm text-primary [&:not(:first-child)]:mt-3" {...props} />,
  h2: (props) => <h3 className="font-headline-sm text-headline-sm text-primary [&:not(:first-child)]:mt-3" {...props} />,
  h3: (props) => <h4 className="font-body-md text-body-md font-semibold text-primary [&:not(:first-child)]:mt-3" {...props} />,
  h4: (props) => <h4 className="font-body-md text-body-md font-semibold text-primary [&:not(:first-child)]:mt-2" {...props} />,
  h5: (props) => <h5 className="font-body-md text-body-md font-semibold [&:not(:first-child)]:mt-2" {...props} />,
  h6: (props) => <h6 className="font-body-md text-body-md font-semibold [&:not(:first-child)]:mt-2" {...props} />,
  strong: (props) => <strong className="font-semibold text-primary" {...props} />,
  ul: (props) => <ul className="list-disc pl-5 mt-2 flex flex-col gap-0.5 font-body-md text-body-md" {...props} />,
  ol: (props) => <ol className="list-decimal pl-5 mt-2 flex flex-col gap-0.5 font-body-md text-body-md" {...props} />,
  a: (props) => <a className="text-secondary underline underline-offset-2" target="_blank" rel="noreferrer noopener" {...props} />,
  hr: () => <hr className="my-3 border-surface-container" />,
  blockquote: (props) => <blockquote className="mt-2 border-l-4 border-secondary-container pl-3 text-on-surface-variant" {...props} />,
  code: (props) => <code className="rounded bg-surface-container px-1 font-label-sm text-label-sm" {...props} />,
  pre: (props) => <pre className="mt-2 overflow-x-auto rounded-[14px] bg-surface-container-low p-space-sm font-label-sm text-label-sm" {...props} />,
  table: (props) => (
    <div className="mt-2 max-w-full overflow-x-auto rounded-[14px] border border-surface-container">
      <table className="w-max min-w-full border-collapse font-label-sm text-label-sm" {...props} />
    </div>
  ),
  thead: (props) => <thead className="bg-surface-container-low" {...props} />,
  th: (props) => <th className="px-2.5 py-1.5 text-left font-label-md text-label-md text-on-surface-variant whitespace-nowrap" {...props} />,
  td: (props) => <td className="px-2.5 py-1.5 border-t border-surface-container text-on-surface" {...props} />,
};

/** Assistant text as markdown (GFM). Think markup is stripped first; raw HTML is never rendered. */
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="min-w-0 break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {sanitizeReply(text)}
      </ReactMarkdown>
    </div>
  );
}
