import { ChatDetails, UploadDocumentResponseStatusEnum } from '@/api';
import { apiClient } from '@/lib/api/client';
import _ from 'lodash';
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

export type Attachment = {
  id: string;
  file: File;
  progress_status:
    | 'pending'
    | 'uploading'
    | 'uploaded'
    | 'indexing'
    | 'success'
    | 'failed';

  document_id?: string;
  filename?: string;
  size?: number;
  status?: UploadDocumentResponseStatusEnum;
  previewUrl?: string;
};

const isImageFile = (file: File) =>
  file.type.startsWith('image/') ||
  /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name);

export const useChatAttachments = (chat: ChatDetails) => {
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  const addFilesToAttachments = useCallback(
    (files: File[]) => {
      if (attachments.length > 0) {
        toast.error('一次只能上传 1 个附件，请先删除当前附件。');
        return;
      }
      if (files.length > 1) {
        toast.error('一次只能上传 1 个附件。');
      }
      const [nextFile] = files;
      if (!nextFile) return;

      setAttachments((attachments) => {
        if (attachments.length > 0) return attachments;
        const newAttachment: Attachment = {
          id: crypto.randomUUID(),
          file: nextFile,
          progress_status: 'pending',
        };
        // Generate preview URL for pasted images immediately
        if (isImageFile(nextFile)) {
          newAttachment.previewUrl = URL.createObjectURL(nextFile);
        }
        return [newAttachment];
      });
    },
    [attachments.length],
  );

  const handleDeleteAttachment = useCallback(async (attachment: Attachment) => {
    if (attachment.previewUrl) {
      URL.revokeObjectURL(attachment.previewUrl);
    }
    setAttachments((items) =>
      items.filter((item) => item.id !== attachment.id),
    );
  }, []);

  const onFileReject = useCallback((file: File, message: string) => {
    toast.error(message, {
      description: `"${file.name.length > 20 ? `${file.name.slice(0, 20)}...` : file.name}" 上传失败`,
    });
  }, []);

  const onFileValidate = useCallback(
    (file: File): string | null => {
      const exists = attachments.some(
        (attachment) =>
          attachment.file.name === file.name &&
          attachment.file.size === file.size &&
          attachment.file.lastModified === file.lastModified,
      );
      if (exists) return '该文件已存在。';
      return null;
    },
    [attachments],
  );

  const prevPendingIdsRef = useRef<Set<string>>(new Set());

  const attachmentsRef = useRef<Attachment[]>([]);
  attachmentsRef.current = attachments;

  const checkAttachmentStatus = useCallback(async () => {
    const items = attachmentsRef.current;
    const chatId = chat.id;
    if (!chatId) return;
    const toCheck = items.filter((a) => {
      return (
        ['uploaded', 'indexing'].includes(a.progress_status) && a.document_id
      );
    });
    if (toCheck.length === 0) return;
    await Promise.all(
      toCheck.map(async (attachment) => {
        const res =
          await apiClient.chatDocumentsApi.chatsChatIdDocumentsDocumentIdGet({
            chatId,
            documentId: attachment.document_id || '',
          });
        if (res.data) {
          setAttachments((prev) => {
            const item = prev.find((i) => i.id === attachment.id);
            if (!item) return prev;
            let next: Attachment['progress_status'] = 'indexing';
            switch (res.data.status) {
              case 'COMPLETE':
                next = 'success';
                break;
              case 'FAILED':
                next = 'failed';
                break;
            }
            if (item.progress_status === next) return prev;
            item.progress_status = next;
            return [...prev];
          });
        }
      }),
    );
  }, [chat.id]);

  const onAttachmentsChange = useCallback(async () => {
    const chatId = chat.id;
    if (!chatId) return;
    const currentAttachments = attachmentsRef.current;
    const currentPending = currentAttachments.filter(
      (a) => a.progress_status === 'pending' && !a.document_id,
    );
    const newPending = currentPending.filter(
      (a) => !prevPendingIdsRef.current.has(a.id),
    );
    if (newPending.length === 0) return;
    newPending.forEach((a) => prevPendingIdsRef.current.add(a.id));
    await Promise.all(
      newPending.map(async (attachment) => {
        const file = attachment.file;
        const res = await apiClient.chatDocumentsApi.chatsChatIdDocumentsPost({
          chatId,
          file,
          messageId: '',
        });
        if (res.data.id) {
          setAttachments((items) => {
            const item = items.find((item) => item.id === attachment.id);
            if (!item) return items;
            item.document_id = res.data.id;
            item.progress_status = isImageFile(item.file)
              ? 'success'
              : 'uploaded';
            if (isImageFile(item.file)) {
              item.previewUrl = URL.createObjectURL(item.file);
            }
            return [...items];
          });
        }
      }),
    );
  }, [chat.id]);

  useEffect(() => {
    onAttachmentsChange();
  }, [attachments, onAttachmentsChange]);

  const handlePaste = useCallback(
    (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
      if (attachments.length > 0) {
        toast.error('一次只能上传 1 个附件，请先删除当前附件。');
        return;
      }
      const files: File[] = [];
      Array.from(event.clipboardData.items).forEach((item, index) => {
        if (!item.type.startsWith('image/')) return;
        const file = item.getAsFile();
        if (!file) return;
        const extension = item.type.split('/')[1] || 'png';
        files.push(
          new File(
            [file],
            `pasted-screenshot-${Date.now()}-${index}.${extension}`,
            {
              type: item.type,
              lastModified: Date.now(),
            },
          ),
        );
      });
      if (files.length > 0) {
        event.preventDefault();
        addFilesToAttachments(files);
        toast.success('截图已添加为附件，请等待上传完成后发送。');
      }
    },
    [addFilesToAttachments, attachments.length],
  );

  const handleFilesChange = (files: File[]) => {
    setAttachments((attachments) => {
      if (files.length > 1) {
        toast.error('一次只能上传 1 个附件。');
      }
      const data: Attachment[] = [];
      files.slice(0, 1).forEach((file) => {
        const attachment = attachments.find((attachment) =>
          _.isEqual(attachment.file, file),
        );
        data.push({
          id: crypto.randomUUID(),
          file,
          progress_status: 'pending',
          ...attachment,
        });
      });
      return data;
    });
  };

  return {
    attachments,
    setAttachments,
    handleDeleteAttachment,
    onFileReject,
    onFileValidate,
    handlePaste,
    handleFilesChange,
  };
};
