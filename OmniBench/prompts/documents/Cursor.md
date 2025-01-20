# Cursor Software Features Summary

## Composer
- **Access**: Use `⌘I` to open Composer.
- **Create New Composer**: Use `⌘N` to create a new instance.
- **Agent Mode**: Enable with `⌘.` for proactive codebase interaction.
- **Context Exploration**: Type `@` to see context options and use `#` followed by a filename for specific file focus.
- **Context Pills**: Manage active context at the top of the chat.
- **Code Generation and Application**: Review changes in the diff view and accept/reject with provided buttons.
- **Checkpoints**: Generate checkpoints for code versions and revert using `checkout`.
- **History**: Access previous sessions with `⌘+⌥+L` or `Ctrl+Alt+L`.

## Chat
- **Access**: Toggle the AI pane with `Ctrl/⌘ + L`.
- **User and AI Messages**: Submit queries and receive AI responses in a chat thread.
- **Chat History**: View and manage chat threads with `Ctrl/⌘ + Alt/Option + L`.
- **Default Context**: Includes the current file; remove file pill to exclude.
- **Adding Context**: Add custom context with @ symbols.
- **AI Fix in Chat**: Fix linter errors with the AI fix button or `Ctrl/⌘ + Shift + E`.

## Cmd K (Ctrl K)
- **Prompt Bar**: Access by pressing `Ctrl/Cmd K` for code generation or edits.
- **Inline Generation**: Generate new code without code selection.
- **Inline Edits**: Select code and edit directly in the prompt bar.
- **Follow-up Instructions**: Refine prompts and regenerate with `Enter`.
- **Default Context**: Cursor automatically includes useful information.

## Cursor Tab
- **Autocomplete**: Suggest diffs and edits around the cursor.
- **UI Interaction**: Accept suggestions with `Tab`, reject with `Esc`, or partially accept word-by-word with `Ctrl/⌘ →`.
- **Toggling**: Enable or disable the feature from the status bar icon.
- **Settings**: Disable for comments in `Cursor Settings` > `Tab Completion`.