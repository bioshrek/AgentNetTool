import type { ForgeConfig } from '@electron-forge/shared-types';
import { MakerSquirrel } from '@electron-forge/maker-squirrel';
import { MakerZIP } from '@electron-forge/maker-zip';
import { MakerDeb } from '@electron-forge/maker-deb';
import { MakerRpm } from '@electron-forge/maker-rpm';
import { MakerAppImage } from '@reforged/maker-appimage';
import { AutoUnpackNativesPlugin } from '@electron-forge/plugin-auto-unpack-natives';
import { WebpackPlugin } from '@electron-forge/plugin-webpack';
import { FusesPlugin } from '@electron-forge/plugin-fuses';
import { FuseV1Options, FuseVersion } from '@electron/fuses';

import { mainConfig } from './webpack.main.config';
import { rendererConfig } from './webpack.renderer.config';
import { exec } from 'child_process';
import util from 'util';

const execAsync = util.promisify(exec);

const _osxSign = process.platform === 'darwin' ? {} : undefined;
const _osxNotarize = process.platform === 'darwin' ? {
  appleId: process.env.APPLE_ID,
  appleIdPassword: process.env.APPLE_PASSWORD,
  teamId: process.env.APPLE_TEAM_ID
} : undefined;

const config: ForgeConfig = {
  packagerConfig: {
    asar: true,
    name: 'agentnet-annotator',
    executableName: 'agentnet-annotator',
    icon: './src/assets/icon',
    extraResource: [
      'api/dist/backend/'
    ],
    osxSign: _osxSign,
    osxNotarize: _osxNotarize,
    protocols: [
      {
        name: 'agentnet',
        schemes: ['agentnet'],
      },
    ]
  },
  hooks: {
    prePackage: async () => {
      console.log('Building Flask Backend via uv...');
      /*
      try {
        const { stdout, stderr } = await execAsync('pnpm run build-flask');
        console.log(stdout);
        if (stderr) console.error(stderr);
        console.log('Flask backend built successfully.');
      } catch (err: any) {
        console.error('Failed to build Flask backend:', err);
        if (err.stdout) console.log('stdout:', err.stdout);
        if (err.stderr) console.error('stderr:', err.stderr);
        throw err;
      }
      */
    }
  },
  rebuildConfig: {},
  makers: [
    /*
    new MakerSquirrel({}), 
    new MakerZIP({}, ['darwin']), 
    new MakerRpm({
      options: {
        bin: 'agentnet-annotator'
      }
    }), 
    new MakerDeb({
      options: {
        bin: 'agentnet-annotator'
      }
    }),
    */
    new MakerAppImage({
      options: {
        bin: 'agentnet-annotator'
      }
    }, ['linux']),
    /*
    {
      name: '@electron-forge/maker-dmg',
      config: {
        format: 'ULFO'
      }
    }
    */
  ],
  plugins: [
    new AutoUnpackNativesPlugin({}),
    new WebpackPlugin({
      mainConfig,
      devContentSecurityPolicy: "connect-src 'self' * 'unsafe-eval'",
      renderer: {
        config: rendererConfig,
        
        entryPoints: [
          {
            html: './src/index.html',
            js: './src/renderer.ts',
            name: 'main_window',
            preload: {
              js: './src/preload.ts',
            },
          },
        ],
      },
    }),
    // Fuses are used to enable/disable various Electron functionality
    // at package time, before code signing the application
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};

export default config;
