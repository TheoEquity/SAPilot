'use client';

import { useCallback, useEffect, useState } from 'react';

import type {
  CollectionOutput as Collection,
  SharingStatusResponse,
} from '@/api/generated/models';
import { apiClient } from '@/lib/api/client';
import { createContext, useContext } from 'react';

type CollectionContextProps = {
  collection: Collection;
  share?: SharingStatusResponse;
  loadShare: () => void;

  loadCollection: () => void;
};

const CollectionContext = createContext<CollectionContextProps>({
  collection: {},
  share: {
    is_published: false,
  },
  loadShare: () => {},
  loadCollection: () => {},
});

export const useCollectionContext = () => useContext(CollectionContext);

export const CollectionProvider = ({
  collection: initCollection,
  share: initShare,
  children,
}: {
  children?: React.ReactNode;
  collection: Collection;
  share?: SharingStatusResponse;
}) => {
  const [share, setShare] = useState<SharingStatusResponse | undefined>(
    initShare,
  );
  const [collection, setCollection] = useState<Collection>(initCollection);

  const loadShare = useCallback(async () => {
    if (!collection?.id) {
      return;
    }
    const res =
      await apiClient.collections.getCollectionSharingStatusApiV1CollectionsCollectionIdSharingGet(
        encodeURIComponent(String(collection.id)),
      );
    setShare(res.data);
  }, [collection?.id]);

  const loadCollection = useCallback(async () => {
    if (!collection?.id) {
      return;
    }
    const res =
      await apiClient.collections.getCollectionViewApiV1CollectionsCollectionIdGet(
        encodeURIComponent(String(collection.id)),
      );
    setCollection(res.data);
  }, [collection?.id]);

  useEffect(() => {
    setCollection(initCollection);
  }, [initCollection]);

  useEffect(() => {
    setShare(initShare);
  }, [initShare]);

  return (
    <CollectionContext.Provider
      value={{ collection, share, loadShare, loadCollection }}
    >
      {children}
    </CollectionContext.Provider>
  );
};
