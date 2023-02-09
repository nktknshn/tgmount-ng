class FileSystemOperationsMixin:
    def get_inodes_tree(
        self: "FileSystemOperations", inode=InodesRegistry.ROOT_INODE  # type: ignore
    ) -> InodesTree:
        item = self.inodes.get_item_by_inode(inode)

        if item is None:
            raise ValueError(f"item with {inode} was not found")

        inodes = self.inodes

        path = none_fallback(inodes.get_item_path(inode), [])

        children = None
        if self.inodes.was_content_read(inode):
            children = []
            children_items = inodes.get_items_by_parent(inode)

            if children_items is None:
                children_items = []

            for child in children_items:
                if isinstance(child.data.structure_item, vfs.DirLike):
                    children.append(self.get_inodes_tree(child.inode))
                else:
                    path = [*path, child.name]
                    children.append(
                        InodesTreeFile(
                            inode=child.inode,
                            path=list(map(self._bytes_to_str, path)),
                            path_str=inodes.join_path(path).decode("utf-8"),
                            name=self._bytes_to_str(child.name),
                            extra=child.data.structure_item.extra,
                        )
                    )

        return InodesTree(
            inode=inode,
            name=self._bytes_to_str(item.name),
            path=list(map(self._bytes_to_str, path)),
            path_str=self._bytes_to_str(inodes.join_path(path)),
            children=children,
            extra=item.data.structure_item.extra,
        )
