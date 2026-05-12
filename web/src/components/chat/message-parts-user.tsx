import { ChatMessage } from '@/api';
import { Markdown } from '@/components/markdown';
import { UserRound } from 'lucide-react';
import { MessageTimestamp } from './message-timestamp';

export const MessagePartsUser = ({ parts }: { parts: ChatMessage[] }) => {
  const files = parts?.flatMap(part => part.files || []).filter(Boolean);
  
  return (
    <div className="ml-auto flex w-max flex-row gap-4">
      <div className="flex max-w-sm flex-col gap-2 sm:max-w-lg md:max-w-2xl lg:max-w-3xl xl:max-w-4xl">
        <div className="bg-primary text-primary-foreground rounded-lg p-4 text-sm">
          <Markdown>{parts?.map((part) => part.data || '').join('')}</Markdown>
        </div>
        {files.length > 0 && (
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {files.map((file, index) => (
              file.previewUrl && (
                <div key={index} className="relative">
                  <img 
                    src={file.previewUrl}
                    alt={file.name}
                    className="max-h-8 max-w-8 cursor-pointer rounded border border-primary/30 object-contain"
                    onClick={(e) => {
                      e.stopPropagation();
                      // Use the same preview logic as MonkeyCode
                      const img = e.target as HTMLImageElement;
                      const overlay = document.createElement('div');
                      overlay.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm';
                      const container = document.createElement('div');
                      container.className = 'relative max-h-full max-w-full';
                      const previewImg = document.createElement('img');
                      previewImg.src = img.src;
                      previewImg.className = 'max-h-[80vh] max-w-[80vw] object-contain';
                      const closeBtn = document.createElement('button');
                      closeBtn.innerHTML = '×';
                      closeBtn.className = 'absolute top-4 right-4 z-10 size-8 cursor-pointer rounded-full bg-black/50 text-white text-2xl font-bold';
                      closeBtn.onclick = () => document.body.removeChild(overlay);
                      container.appendChild(previewImg);
                      container.appendChild(closeBtn);
                      overlay.appendChild(container);
                      document.body.appendChild(overlay);
                      
                      // Add wheel zoom like MonkeyCode
                      let scale = 1;
                      previewImg.onwheel = (e) => {
                        e.preventDefault();
                        scale += e.deltaY * -0.01;
                        scale = Math.min(Math.max(0.5, scale), 3);
                        previewImg.style.transform = `scale(${scale})`;
                        previewImg.style.transformOrigin = 'center center';
                      };
                    }}
                  />
                </div>
              )
            ))}
          </div>
        )}
        <MessageTimestamp parts={parts} />
      </div>
      <div>
        <div className="bg-muted text-muted-foreground flex size-12 flex-col justify-center rounded-full">
          <UserRound className="size-5 self-center" />
        </div>
      </div>
    </div>
  );
};
