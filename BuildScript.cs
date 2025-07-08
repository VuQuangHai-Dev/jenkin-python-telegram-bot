using UnityEditor;
using UnityEngine;
using System;
using System.IO;
using System.Linq;
using UnityEditor.Build.Reporting;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Reflection;

public class BuildScript
{
    // --- COMMON CONFIGURATION ---
    private static string buildPrefix = Environment.GetEnvironmentVariable("BUILD_PREFIX");
    private static string buildDir = Environment.GetEnvironmentVariable("BUILD_DIR") ?? Path.Combine(Environment.GetEnvironmentVariable("WORKSPACE") ?? ".", "Builds");

    // --- ANDROID BUILD METHODS ---
    public static void BuildAndroid()
    {
        // Legacy method for backward compatibility - delegates to APK build
        BuildAndroidAPK();
    }

    public static void BuildAndroidAPK()
    {
        Debug.Log("=== JENKINS ANDROID APK BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupAndroidAPKBuildSettings();
            string outputPath = GenerateOutputPath("apk", "apk");
            BuildPlayerAndroid(outputPath);
            Debug.Log($"✅ Android APK build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Android APK build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    public static void BuildAndroidAAB()
    {
        Debug.Log("=== JENKINS ANDROID AAB BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupAndroidAABBuildSettings();
            string outputPath = GenerateOutputPath("aab", "aab");
            BuildPlayerAndroid(outputPath);
            Debug.Log($"✅ Android AAB build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Android AAB build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    public static void BuildAndroidDevelopment()
    {
        Debug.Log("=== JENKINS ANDROID DEVELOPMENT APK BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupAndroidDevelopmentBuildSettings();
            string outputPath = GenerateOutputPath("apk", "apk"); // Development is always APK
            BuildPlayerAndroid(outputPath);
            Debug.Log($"✅ Android Development build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Android Development build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    // --- IOS BUILD METHODS ---
    public static void BuildIOS()
    {
        Debug.Log("=== JENKINS IOS IPA BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupIOSBuildSettings();
            string outputPath = GenerateOutputPath("ipa", "ipa");
            BuildPlayerIOS(outputPath);
            Debug.Log($"✅ iOS build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ iOS build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    public static void BuildIOSDevelopment()
    {
        Debug.Log("=== JENKINS IOS DEVELOPMENT IPA BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupIOSDevelopmentBuildSettings();
            string outputPath = GenerateOutputPath("ipa", "ipa");
            BuildPlayerIOS(outputPath);
            Debug.Log($"✅ iOS Development build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ iOS Development build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    public static void BuildIOSAppStore()
    {
        Debug.Log("=== JENKINS IOS APP STORE BUILD START ===");

        try
        {
            ResolveDependencies();
            SetupIOSAppStoreBuildSettings();
            string outputPath = GenerateOutputPath("ipa", "ipa");
            BuildPlayerIOS(outputPath);
            Debug.Log($"✅ iOS App Store build completed successfully: {outputPath}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ iOS App Store build failed: {e.Message}");
            Debug.LogError($"Stack trace: {e.StackTrace}");
            EditorApplication.Exit(1);
        }
    }

    // --- DEPENDENCY RESOLUTION ---
    private static void ResolveDependencies()
    {
        Debug.Log("--- Resolving Dependencies with EDM4U ---");

        try
        {
            Assembly jarResolverAssembly = null;
            foreach (var assembly in System.AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.FullName.Contains("Google.JarResolver"))
                {
                    jarResolverAssembly = assembly;
                    break;
                }
            }

            if (jarResolverAssembly == null)
            {
                Debug.LogWarning("⚠️ Google.JarResolver assembly not found, skipping dependency resolution");
                return;
            }

            Type resolverType = jarResolverAssembly.GetType("GooglePlayServices.PlayServicesResolver");
            if (resolverType == null)
            {
                Debug.LogWarning("⚠️ PlayServicesResolver type not found, skipping dependency resolution");
                return;
            }

            MethodInfo resolveSyncMethod = resolverType.GetMethod("ResolveSync", new Type[] { typeof(bool) });
            if (resolveSyncMethod == null)
            {
                Debug.LogWarning("⚠️ ResolveSync method not found, skipping dependency resolution");
                return;
            }

            Debug.Log("🔄 Calling EDM4U ResolveSync...");
            resolveSyncMethod.Invoke(null, new object[] { true });
            Debug.Log("✅ EDM4U dependency resolution completed");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"⚠️ EDM4U dependency resolution failed: {e.Message}");
            Debug.LogWarning("Continuing build without EDM4U resolution...");
        }
    }

    // --- ANDROID BUILD SETTINGS ---
    private static void SetupAndroidAPKBuildSettings()
    {
        Debug.Log("--- Setting up Android APK build settings ---");

        EditorUserBuildSettings.buildAppBundle = false; // Force APK
        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
        EditorUserBuildSettings.connectProfiler = false;
        EditorUserBuildSettings.buildScriptsOnly = false;

        // ✅ SET ANDROID RELEASE CONFIGURATION (Publishing Settings)
        PlayerSettings.Android.minifyDebug = false;   // Disable Debug in Minify section
        PlayerSettings.Android.minifyRelease = true;  // Enable Release in Minify section

        Debug.Log($"Build App Bundle: {EditorUserBuildSettings.buildAppBundle} (APK)");
        Debug.Log($"Development: {EditorUserBuildSettings.development}");
        Debug.Log($"Android Minify Release: {PlayerSettings.Android.minifyRelease}");

        SetupAndroidKeystore();
        ConfigureAndroidToolPaths();
    }

    private static void SetupAndroidAABBuildSettings()
    {
        Debug.Log("--- Setting up Android AAB build settings ---");

        EditorUserBuildSettings.buildAppBundle = true; // Force AAB
        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
        EditorUserBuildSettings.connectProfiler = false;
        EditorUserBuildSettings.buildScriptsOnly = false;

        // ✅ SET ANDROID RELEASE CONFIGURATION (Publishing Settings)
        PlayerSettings.Android.minifyDebug = false;   // Disable Debug in Minify section
        PlayerSettings.Android.minifyRelease = true;  // Enable Release in Minify section

        Debug.Log($"Build App Bundle: {EditorUserBuildSettings.buildAppBundle} (AAB)");
        Debug.Log($"Development: {EditorUserBuildSettings.development}");
        Debug.Log($"Android Minify Release: {PlayerSettings.Android.minifyRelease}");

        SetupAndroidKeystore();
        ConfigureAndroidToolPaths();
    }

    private static void SetupAndroidDevelopmentBuildSettings()
    {
        Debug.Log("--- Setting up Android Development build settings ---");

        EditorUserBuildSettings.buildAppBundle = false; // Development builds are always APK
        EditorUserBuildSettings.development = true;
        EditorUserBuildSettings.allowDebugging = true;
        EditorUserBuildSettings.connectProfiler = true;
        EditorUserBuildSettings.buildScriptsOnly = false;
        EditorUserBuildSettings.waitForManagedDebugger = true; // Wait for managed debugger

        // Enable script debugging
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64; // Recommended for debugging

        // ✅ SET ANDROID DEBUG CONFIGURATION (Publishing Settings)
        PlayerSettings.Android.minifyDebug = true;    // Enable Debug in Minify section
        PlayerSettings.Android.minifyRelease = false; // Disable Release in Minify section
        PlayerSettings.SetStackTraceLogType(LogType.Log, StackTraceLogType.ScriptOnly);
        PlayerSettings.SetStackTraceLogType(LogType.Warning, StackTraceLogType.ScriptOnly);
        PlayerSettings.SetStackTraceLogType(LogType.Error, StackTraceLogType.Full);

        Debug.Log($"Build App Bundle: {EditorUserBuildSettings.buildAppBundle}");
        Debug.Log($"Development: {EditorUserBuildSettings.development}");
        Debug.Log($"Allow Debugging: {EditorUserBuildSettings.allowDebugging}");
        Debug.Log($"Connect Profiler: {EditorUserBuildSettings.connectProfiler}");
        Debug.Log($"Wait for Managed Debugger: {EditorUserBuildSettings.waitForManagedDebugger}");
        Debug.Log($"Android Minify Debug: {PlayerSettings.Android.minifyDebug}");
        Debug.Log($"Script Debugging: ENABLED");

        SetupAndroidKeystore();
        ConfigureAndroidToolPaths();
    }

    // --- IOS BUILD SETTINGS ---
    private static void SetupIOSBuildSettings()
    {
        Debug.Log("--- Setting up iOS build settings ---");

        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
        EditorUserBuildSettings.connectProfiler = false;
        EditorUserBuildSettings.buildScriptsOnly = false;

        Debug.Log($"Development: {EditorUserBuildSettings.development}");

        ConfigureIOSSettings();
    }

    private static void SetupIOSDevelopmentBuildSettings()
    {
        Debug.Log("--- Setting up iOS Development build settings ---");

        EditorUserBuildSettings.development = true;
        EditorUserBuildSettings.allowDebugging = true;
        EditorUserBuildSettings.connectProfiler = true;
        EditorUserBuildSettings.buildScriptsOnly = false;
        EditorUserBuildSettings.waitForManagedDebugger = true; // Wait for managed debugger

        // Enable script debugging for iOS
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.iOS, ScriptingImplementation.IL2CPP);

        Debug.Log($"Development: {EditorUserBuildSettings.development}");
        Debug.Log($"Allow Debugging: {EditorUserBuildSettings.allowDebugging}");
        Debug.Log($"Connect Profiler: {EditorUserBuildSettings.connectProfiler}");
        Debug.Log($"Wait for Managed Debugger: {EditorUserBuildSettings.waitForManagedDebugger}");
        Debug.Log($"Script Debugging: ENABLED");

        ConfigureIOSSettings();
    }

    private static void SetupIOSAppStoreBuildSettings()
    {
        Debug.Log("--- Setting up iOS App Store build settings ---");

        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
        EditorUserBuildSettings.connectProfiler = false;
        EditorUserBuildSettings.buildScriptsOnly = false;

        Debug.Log($"Development: {EditorUserBuildSettings.development}");

        ConfigureIOSAppStoreSettings();
    }

    // --- ANDROID CONFIGURATION ---
    private static void SetupAndroidKeystore()
    {
        // Use Jenkins credentials variable names
        var keystorePath = Environment.GetEnvironmentVariable("KEYSTORE");
        var keystorePass = Environment.GetEnvironmentVariable("KEYSTORE_PASS");
        var keyAliasName = Environment.GetEnvironmentVariable("ALIAS_NAME");
        var keyAliasPass = Environment.GetEnvironmentVariable("ALIAS_PASS");

        if (!string.IsNullOrEmpty(keystorePath) && File.Exists(keystorePath))
        {
            PlayerSettings.Android.keystoreName = keystorePath;
            PlayerSettings.Android.keystorePass = keystorePass ?? "";
            PlayerSettings.Android.keyaliasName = keyAliasName ?? "";
            PlayerSettings.Android.keyaliasPass = keyAliasPass ?? "";

            Debug.Log($"✅ Android keystore configured: {keystorePath}");
        }
        else
        {
            Debug.LogWarning($"⚠️ Android keystore not found: {keystorePath}");
        }
    }

    private static void ConfigureAndroidToolPaths()
    {
        var androidSdkRoot = Environment.GetEnvironmentVariable("ANDROID_SDK_ROOT");
        var androidNdkRoot = Environment.GetEnvironmentVariable("ANDROID_NDK_ROOT");
        var javaHome = Environment.GetEnvironmentVariable("JAVA_HOME");
        var gradlePath = Environment.GetEnvironmentVariable("GRADLE_PATH");

        if (!string.IsNullOrEmpty(androidSdkRoot))
        {
            EditorPrefs.SetString("AndroidSdkRoot", androidSdkRoot);
            Debug.Log($"Android SDK Root: {androidSdkRoot}");
        }

        if (!string.IsNullOrEmpty(androidNdkRoot))
        {
            EditorPrefs.SetString("AndroidNdkRoot", androidNdkRoot);
            Debug.Log($"Android NDK Root: {androidNdkRoot}");
        }

        if (!string.IsNullOrEmpty(javaHome))
        {
            EditorPrefs.SetString("JdkPath", javaHome);
            Debug.Log($"Java Home: {javaHome}");
        }

        if (!string.IsNullOrEmpty(gradlePath))
        {
            EditorPrefs.SetString("GradlePath", gradlePath);
            Debug.Log($"Gradle Path: {gradlePath}");
        }
    }

    // --- IOS CONFIGURATION ---
    private static void ConfigureIOSSettings()
    {
        var teamId = Environment.GetEnvironmentVariable("IOS_TEAM_ID");
        var provisionProfile = Environment.GetEnvironmentVariable("IOS_PROVISION_PROFILE");

        if (!string.IsNullOrEmpty(teamId))
        {
            PlayerSettings.iOS.appleDeveloperTeamID = teamId;
            Debug.Log($"iOS Team ID: {teamId}");
        }

        if (!string.IsNullOrEmpty(provisionProfile))
        {
            PlayerSettings.iOS.iOSManualProvisioningProfileID = provisionProfile;
            Debug.Log($"iOS Provisioning Profile: {provisionProfile}");
        }

        Debug.Log("iOS Build Configuration: Release");
    }

    private static void ConfigureIOSAppStoreSettings()
    {
        ConfigureIOSSettings(); // Use base iOS settings

        // Additional App Store specific settings
        Debug.Log("iOS Build Configuration: Release (App Store)");
    }

    // --- OUTPUT PATH GENERATION ---
    private static string GenerateOutputPath(string apkExtension, string aabExtension)
    {
        var buildType = Environment.GetEnvironmentVariable("BUILD_TYPE");
        var gitBranchRaw = Environment.GetEnvironmentVariable("GIT_BRANCH") ?? "unknown-branch";
        var gitBranch = gitBranchRaw.Replace("origin/", "");

        var config = Environment.GetEnvironmentVariable("CONFIG");
        var extension = (buildType == "AAB") ? aabExtension : apkExtension;

        Directory.CreateDirectory(buildDir);

        var dateStr = DateTime.Now.ToString("yyMMdd");

        // Generate filename based on build type and platform
        string baseFileName;
        string searchPattern;

        if (buildType == "AAB")
        {
            // Android AAB format: {buildPrefix}-{branch}_{version}_{bundleVersionCode}
            var bundleVersionCode = PlayerSettings.Android.bundleVersionCode;
            var appVersion = PlayerSettings.bundleVersion;
            baseFileName = $"{buildPrefix}-{gitBranch}_{appVersion}_{bundleVersionCode}";
            searchPattern = $"{buildPrefix}-{gitBranch}_{appVersion}_{bundleVersionCode}*.{extension}";

            Debug.Log($"Android AAB naming: prefix={buildPrefix}, branch={gitBranch}, version={appVersion}, bundleCode={bundleVersionCode}");
        }
        else if (extension == "apk")
        {
            // Android APK format: {buildPrefix}-{branch}_{dateStr}[_debug] 
            var debugSuffix = (config == "Development") ? "_debug" : "";
            baseFileName = $"{buildPrefix}-{gitBranch}_{dateStr}{debugSuffix}";
            searchPattern = $"{buildPrefix}-{gitBranch}_{dateStr}{debugSuffix}_*.{extension}";

            Debug.Log($"Android APK naming: prefix={buildPrefix}, branch={gitBranch}, date={dateStr}, debug={config == "Development"}");
        }
        else
        {
            // iOS format: Keep original format {buildPrefix}_{dateStr} (no branch suffix for now)
            var branchSuffix = gitBranch != "master" ? $"-{gitBranch}" : "";
            baseFileName = $"{buildPrefix}{branchSuffix}_{dateStr}";
            searchPattern = $"{baseFileName}_*.{extension}";

            Debug.Log($"iOS naming: prefix={buildPrefix}, branch={gitBranch}, date={dateStr}");
        }

        // Find existing files with same pattern
        var existingFiles = Directory.GetFiles(buildDir, searchPattern)
                                   .Select(f => Path.GetFileNameWithoutExtension(f))
                                   .ToList();

        Debug.Log($"Found {existingFiles.Count} existing files with pattern {searchPattern}");
        Debug.Log($"Building from git branch: {gitBranch}");

        // Extract version numbers and find the next available number
        int nextVersion = 1;
        var pattern = $@"^{System.Text.RegularExpressions.Regex.Escape(baseFileName)}_(\d+)$";
        var regex = new System.Text.RegularExpressions.Regex(pattern);

        foreach (var fileName in existingFiles)
        {
            var match = regex.Match(fileName);
            if (match.Success && int.TryParse(match.Groups[1].Value, out int version))
            {
                if (version >= nextVersion)
                {
                    nextVersion = version + 1;
                }
            }
        }

        var finalFileName = $"{baseFileName}_{nextVersion:D2}.{extension}";
        var outputPath = Path.Combine(buildDir, finalFileName);

        Debug.Log($"Generated output path: {outputPath}");
        Debug.Log($"Using version number: {nextVersion:D2}");
        Debug.Log($"Git branch: {gitBranch}");
        Debug.Log($"Build type: {buildType}, Config: {config}");

        return outputPath;
    }

    // --- BUILD EXECUTION ---
    private static void BuildPlayerAndroid(string outputPath)
    {
        Debug.Log($"--- Building Android player to: {outputPath} ---");

        var buildOptions = BuildOptions.None;
        if (EditorUserBuildSettings.development)
        {
            buildOptions |= BuildOptions.Development;
            if (EditorUserBuildSettings.allowDebugging)
                buildOptions |= BuildOptions.AllowDebugging;
            if (EditorUserBuildSettings.connectProfiler)
                buildOptions |= BuildOptions.ConnectWithProfiler;
        }

        var buildPlayerOptions = new BuildPlayerOptions
        {
            scenes = GetScenePaths(),
            locationPathName = outputPath,
            target = BuildTarget.Android,
            options = buildOptions
        };

        var result = BuildPipeline.BuildPlayer(buildPlayerOptions);

        if (result.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            Debug.Log($"✅ Android build succeeded: {outputPath}");
            Debug.Log($"Build size: {result.summary.totalSize} bytes");

            if (EditorUserBuildSettings.development)
            {
                Debug.Log("🔧 Development build features:");
                Debug.Log("   • Script debugging enabled");
                Debug.Log("   • Wait for managed debugger enabled");
                Debug.Log("   • Profiler connection enabled");
            }
        }
        else
        {
            string errorMessage = $"❌ Android build failed: {result.summary.result}";
            if (result.summary.totalErrors > 0)
            {
                errorMessage += $"\nErrors: {result.summary.totalErrors}";
            }
            throw new Exception(errorMessage);
        }
    }

    private static void BuildPlayerIOS(string outputPath)
    {
        Debug.Log($"--- Building iOS player to: {outputPath} ---");

        var buildOptions = BuildOptions.None;
        if (EditorUserBuildSettings.development)
        {
            buildOptions |= BuildOptions.Development;
            if (EditorUserBuildSettings.allowDebugging)
                buildOptions |= BuildOptions.AllowDebugging;
            if (EditorUserBuildSettings.connectProfiler)
                buildOptions |= BuildOptions.ConnectWithProfiler;
        }

        // For iOS, we first build to Xcode project, then can archive to IPA
        var xcodeProjectPath = Path.ChangeExtension(outputPath, null); // Remove .ipa extension for Xcode project

        var buildPlayerOptions = new BuildPlayerOptions
        {
            scenes = GetScenePaths(),
            locationPathName = xcodeProjectPath,
            target = BuildTarget.iOS,
            options = buildOptions
        };

        var result = BuildPipeline.BuildPlayer(buildPlayerOptions);

        if (result.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            Debug.Log($"✅ iOS Xcode project built successfully: {xcodeProjectPath}");
            Debug.Log($"Build size: {result.summary.totalSize} bytes");

            if (EditorUserBuildSettings.development)
            {
                Debug.Log("🔧 Development build features:");
                Debug.Log("   • Script debugging enabled");
                Debug.Log("   • Wait for managed debugger enabled");
                Debug.Log("   • Profiler connection enabled");
            }

            // Note: For actual IPA generation, you would typically use xcodebuild command
            // This would be handled by the bash script after Unity completes
            Debug.Log("📝 Note: Use xcodebuild to archive and export IPA from Xcode project");
        }
        else
        {
            string errorMessage = $"❌ iOS build failed: {result.summary.result}";
            if (result.summary.totalErrors > 0)
            {
                errorMessage += $"\nErrors: {result.summary.totalErrors}";
            }
            throw new Exception(errorMessage);
        }
    }

    // --- HELPER METHODS ---
    private static string[] GetScenePaths()
    {
        return EditorBuildSettings.scenes
            .Where(scene => scene.enabled)
            .Select(scene => scene.path)
            .ToArray();
    }
}