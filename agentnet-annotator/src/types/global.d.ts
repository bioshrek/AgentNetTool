import { Channels } from "..preload";

declare global {
  interface Window {
    electron: {
      ipcRenderer: {
        sendMessage(channel: Channels, ...args: unknown[]): void;
        on(
          channel: string,
          func: (...args: unknown[]) => void
        ): (() => void) | undefined;
        once(channel: string, func: (...args: unknown[]) => void): void;
        off(
          channel: string,
          func: (...args: unknown[]) => void
        ): (() => void) | undefined;
      };
      openDirectoryDialog: (options?: any) => Promise<string | undefined>;
      updateTrayIcon: (iconPath: string) => void;
      updateTrayTitle: (title: string) => void;
    };
  }
}

export {};
