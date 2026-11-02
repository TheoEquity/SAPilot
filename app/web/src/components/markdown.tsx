'use client';

import { cn } from '@/lib/utils';
import { ImageIcon, XIcon } from 'lucide-react';
import Link from 'next/link';
import {
  JSX,
  MouseEvent,
  MouseEventHandler,
  useCallback,
  useEffect,
  useMemo,
  useState,
  WheelEvent,
} from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import rehypeHighlightLines from 'rehype-highlight-code-lines';
import rehypeRaw from 'rehype-raw';
import remarkDirective from 'remark-directive';
import remarkFrontmatter from 'remark-frontmatter';
import remarkGfm from 'remark-gfm';
import remarkGithubAdmonitionsToDirectives from 'remark-github-admonitions-to-directives';
import remarkHeaderId from 'remark-heading-id';
import remarkMdxFrontmatter from 'remark-mdx-frontmatter';
import { AnchorLink } from './anchor-link';
import { ChartMermaid } from './chart-mermaid';
import { Skeleton } from './ui/skeleton';
import { Table, TableBody, TableCell, TableHeader, TableRow } from './ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';

import './markdown.css';

const securityLink = (props: JSX.IntrinsicElements['a']) => {
  const target = props.href?.match(/^http/) ? '_blank' : '_self';
  const url = props.href?.replace(/\.md/, '');

  const isNavLink = props.className?.includes('toc-link');
  return isNavLink ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <AnchorLink {...props} href={url || '/'} target={target} />
      </TooltipTrigger>
      <TooltipContent side={isNavLink ? 'left' : 'top'}>
        {props.children}
      </TooltipContent>
    </Tooltip>
  ) : (
    <Link {...props} href={url || '/'} target={target} className="underline">
      {props.children}
    </Link>
  );
};

const unSecurityLink = (props: JSX.IntrinsicElements['a']) => {
  const url = props.href?.replace(/\.md/, '') || '/';
  const isNavLink = props.className?.includes('toc-link');
  const handleLinkClick: MouseEventHandler<HTMLAnchorElement> = (e) => {
    if (!url.match(/http/)) {
      e.preventDefault();
      e.stopPropagation();
    }
  };
  return isNavLink ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <AnchorLink
          {...props}
          href={url}
          target="_blank"
          onClick={handleLinkClick}
        />
      </TooltipTrigger>
      <TooltipContent side={isNavLink ? 'left' : 'top'}>
        {props.children}
      </TooltipContent>
    </Tooltip>
  ) : (
    <Link
      {...props}
      href={url}
      target="_blank"
      className="underline"
      onClick={handleLinkClick}
    >
      {props.children}
    </Link>
  );
};

export const CustomImage = ({
  src,
  ...props
}: JSX.IntrinsicElements['img']) => {
  const [imageUrl, setImageUrl] = useState<string>();

  const getImageSrc = useCallback(async () => {
    if (typeof src !== 'string') return;
    const [path, queryString] = src.replace('asset://', '').split('?');
    const params = new URLSearchParams(queryString || '');
    const collectionId = params.get('collection_id');
    const documentId = params.get('document_id');

    if (!path || !collectionId || !documentId) return;

    const objectUrl = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/v1/collections/${collectionId}/documents/${documentId}/object?path=${encodeURIComponent(`assets/${path}`)}`;
    const response = await fetch(objectUrl);
    if (!response.ok) return;

    const blob = await response.blob();
    setImageUrl(URL.createObjectURL(blob));
  }, [src]);

  useEffect(() => {
    getImageSrc();
  }, [getImageSrc]);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  return imageUrl ? (
    <ImagePreview imageUrl={imageUrl} alt={props.alt || '图片预览'}>
      <span className="block cursor-zoom-in">
        <img
          {...props}
          alt={props.alt}
          src={imageUrl}
          className="h-auto w-full max-w-none min-w-64 rounded border object-contain"
        />
      </span>
    </ImagePreview>
  ) : (
    <Skeleton className="my-4 h-[125px] w-full rounded-xl py-4 pt-8 text-center">
      <ImageIcon className="mx-auto size-12 opacity-20" />
    </Skeleton>
  );
};

export const ImagePreview = ({
  imageUrl,
  alt,
  children,
}: {
  imageUrl: string;
  alt: string;
  children: React.ReactNode;
}) => {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [scale, setScale] = useState(1);
  const [transformOrigin, setTransformOrigin] = useState('center center');

  const resetPreview = () => {
    setScale(1);
    setTransformOrigin('center center');
  };

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    const step = event.deltaY < 0 ? 1.15 : 1 / 1.15;
    setTransformOrigin(`${x}% ${y}%`);
    setScale((current) => Math.max(0.05, current * step));
  };

  const closePreview = (event?: MouseEvent<HTMLButtonElement>) => {
    event?.stopPropagation();
    setPreviewOpen(false);
    resetPreview();
  };

  useEffect(() => {
    if (!previewOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPreviewOpen(false);
        resetPreview();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [previewOpen]);

  return (
    <>
      <button
        className="block cursor-zoom-in"
        onClick={() => setPreviewOpen(true)}
        type="button"
      >
        {children}
      </button>
      {previewOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm"
          onDoubleClick={resetPreview}
          onWheel={handleWheel}
        >
          <button
            className="bg-background/90 text-foreground hover:bg-background absolute top-4 right-4 z-10 rounded-full p-2 shadow-lg transition-colors"
            onClick={closePreview}
            type="button"
          >
            <XIcon className="size-5" />
            <span className="sr-only">关闭图片预览</span>
          </button>
          <img
            alt={alt}
            className="max-h-[90vh] max-w-[90vw] object-contain select-none"
            draggable={false}
            src={imageUrl}
            style={{
              cursor: 'zoom-in',
              transform: `scale(${scale})`,
              transformOrigin,
            }}
          />
        </div>
      )}
    </>
  );
};

export const mdComponents = {
  h1: (props: JSX.IntrinsicElements['h1']) => (
    <h1 className="my-6 text-5xl font-bold first:mt-0 last:mb-0">
      {props.children}
    </h1>
  ),
  h2: (props: JSX.IntrinsicElements['h2']) => (
    <h2 className="my-5 text-4xl font-bold first:mt-0 last:mb-0">
      {props.children}
    </h2>
  ),
  h3: (props: JSX.IntrinsicElements['h3']) => (
    <h3 className="my-4 text-3xl font-bold first:mt-0 last:mb-0">
      {props.children}
    </h3>
  ),
  h4: (props: JSX.IntrinsicElements['h4']) => (
    <h4 className="my-3 text-2xl font-bold first:mt-0 last:mb-0">
      {props.children}
    </h4>
  ),
  h5: (props: JSX.IntrinsicElements['h5']) => (
    <h5 className="my-2 text-xl font-bold first:mt-0 last:mb-0">
      {props.children}
    </h5>
  ),
  h6: (props: JSX.IntrinsicElements['h6']) => (
    <h6 className="my-2 text-lg font-bold first:mt-0 last:mb-0">
      {props.children}
    </h6>
  ),
  p: (props: JSX.IntrinsicElements['p']) => (
    <div className="my-2 first:mt-0 last:mb-0">{props.children}</div>
  ),
  blockquote: ({
    className,
    ...props
  }: JSX.IntrinsicElements['blockquote']) => {
    return (
      <blockquote
        className={cn(
          'text-muted-foreground my-4 border-l-4 py-1 pl-4 first:mt-0 last:mb-0',
          className,
        )}
      >
        {props.children}
      </blockquote>
    );
  },
  img: ({ src, ...props }: JSX.IntrinsicElements['img']) => {
    if (!src) {
      return (
        <Skeleton className="my-4 h-[125px] w-full rounded-xl py-4 pt-8 text-center">
          <ImageIcon className="mx-auto size-12 opacity-20" />
        </Skeleton>
      );
    } else if (typeof src === 'string' && src.startsWith('asset://')) {
      return <CustomImage src={src} {...props} />;
    } else {
      return (
        <img
          src={src}
          width={props.width}
          height={props.height}
          alt={props.alt}
          title={props.title}
          style={{ maxWidth: '100%', height: 'auto' }}
        />
      );
    }
  },
  pre: ({ className, ...props }: JSX.IntrinsicElements['pre']) => {
    return (
      <pre className={cn('my-4 overflow-x-auto', className)}>
        {props.children}
      </pre>
    );
  },
  code: ({ className, ...props }: JSX.IntrinsicElements['code']) => {
    const match = /language-(\w+)/.exec(className || '');
    const language = match?.[1];
    if (language) {
      if (language === 'mermaid') {
        return (
          <ChartMermaid>
            {typeof props.children === 'string' ? props.children : ''}
          </ChartMermaid>
        );
      } else {
        return (
          <code className={cn('rounded-md text-sm', className)}>
            {props.children}
          </code>
        );
      }
    } else {
      return (
        <code
          className={cn(
            'mx-1 inline-block overflow-x-auto rounded-md bg-gray-500/10 px-1.5 py-0.5 align-middle text-sm',
            className,
          )}
        >
          {props.children}
        </code>
      );
    }
  },
  ol: ({ className, ...props }: JSX.IntrinsicElements['ul']) => {
    return (
      <ul className={cn('my-4 list-decimal pl-4', className)}>
        {props.children}
      </ul>
    );
  },
  ul: ({ className, ...props }: JSX.IntrinsicElements['ul']) => {
    return (
      <ul className={cn('my-4 list-disc pl-4', className)}>{props.children}</ul>
    );
  },
  li: ({ className, ...props }: JSX.IntrinsicElements['li']) => {
    return (
      <li className={cn('my-1 list-item', className)}>{props.children}</li>
    );
  },
  nav: (props: JSX.IntrinsicElements['nav']) => {
    if (props.className === 'toc') {
      return <nav {...props} />;
    } else {
      return <nav {...props} />;
    }
  },
  table: (props: JSX.IntrinsicElements['table']) => (
    <div className="my-4 overflow-hidden rounded-lg border">
      <Table {...props} />
    </div>
  ),
  thead: (props: JSX.IntrinsicElements['thead']) => <TableHeader {...props} />,
  tbody: (props: JSX.IntrinsicElements['tbody']) => <TableBody {...props} />,
  tr: (props: JSX.IntrinsicElements['tr']) => <TableRow {...props} />,
  td: (props: JSX.IntrinsicElements['td']) => (
    <TableCell>{props.children}</TableCell>
  ),
  th: (props: JSX.IntrinsicElements['th']) => (
    <TableCell>{props.children}</TableCell>
  ),
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const mdRehypePlugins: any = [
  rehypeRaw,
  rehypeHighlight,
  rehypeHighlightLines,
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const mdRemarkPlugins: any = [
  remarkGfm,
  remarkFrontmatter,
  remarkMdxFrontmatter,
  remarkGithubAdmonitionsToDirectives,
  remarkDirective,
  [
    remarkHeaderId,
    {
      defaults: true,
    },
  ],
];

export const Markdown = ({
  rehypeToc = false,
  security = false,
  children,
}: {
  rehypeToc?: boolean;
  security?: boolean;
  children?: string;
}) => {
  const rehypePlugins = useMemo(() => {
    const plugins = [...mdRehypePlugins];
    if (rehypeToc) {
      plugins.push([
        rehypeToc,
        {
          headings: ['h2', 'h3', 'h4', 'h5', 'h6'],
        },
      ]);
    }
    return plugins;
  }, [rehypeToc]);

  return (
    <ReactMarkdown
      rehypePlugins={rehypePlugins}
      remarkPlugins={mdRemarkPlugins}
      urlTransform={(url) => url}
      components={{
        a: security ? securityLink : unSecurityLink,
        ...mdComponents,
      }}
    >
      {children}
    </ReactMarkdown>
  );
};
