import React, { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { ExclamationTriangleIcon } from "@heroicons/react/24/outline";

interface ResolutionErrorDialogProps {
  isOpen: boolean;
  onClose: () => void;
  currentResolution?: string;
}

const ResolutionErrorDialog: React.FC<ResolutionErrorDialogProps> = ({
  isOpen,
  onClose,
  currentResolution,
}) => {
  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ExclamationTriangleIcon
                      className="h-6 w-6 text-red-600"
                      aria-hidden="true"
                    />
                  </div>
                  <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                    <Dialog.Title
                      as="h3"
                      className="text-base font-semibold leading-6 text-gray-900"
                    >
                      Invalid Screen Resolution
                    </Dialog.Title>
                    <div className="mt-3">
                      <p className="text-sm text-gray-500 mb-3">
                        由于屏幕分辨率设置得不正确，无法开始录制。
                      </p>
                      {currentResolution && (
                        <div className="bg-gray-50 rounded-md p-3 mb-3">
                          <p className="text-sm">
                            <span className="font-medium text-gray-700">
                              当前分辨率:
                            </span>{" "}
                            <span className="text-red-600 font-semibold">
                              {currentResolution}
                            </span>
                          </p>
                          <p className="text-sm mt-1">
                            <span className="font-medium text-gray-700">
                              所需分辨率:
                            </span>{" "}
                            <span className="text-green-600 font-semibold">
                              1920x1080
                            </span>
                          </p>
                        </div>
                      )}
                      <div className="bg-blue-50 border-l-4 border-blue-400 p-3">
                        <p className="text-sm text-blue-700 font-medium mb-2">
                          解决方法:
                        </p>
                        <ol className="text-sm text-blue-700 list-decimal list-inside space-y-1">
                          <li>
                            客户端：请阅读文档https://my.feishu.cn/docx/Gz6AdsIiDoMM4FxXihpcx7cin8b
                            中设置分辨率章节
                          </li>
                          <li>
                            网页端：请重启云电脑。如果重启之后仍然无法解决，请联系技术支持
                          </li>
                        </ol>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 sm:ml-3 sm:w-auto"
                    onClick={onClose}
                  >
                    知道了
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default ResolutionErrorDialog;
