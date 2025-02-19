import subprocess
import argparse
import os

# adjust these paths if needed
java_path = r'"xxx\java.exe"'
# https://github.com/WindySha/ManifestEditor
manifest_editor_jar = r'"xxx/ManifestEditor-2.0.jar"'
zipalign_path = r'"xxx/zipalign.exe"'
apksigner_jar = r'"xxx/apksigner.jar"'
keystore_path = r'"xxx/yy.keystore"'


def main():
    parser = argparse.ArgumentParser(
        description="Process an APK: make it debuggable, align, and sign it."
    )
    parser.add_argument(
        "input_apk",
        help="Path to the input APK file (e.g., app-release.apk)"
    )
    args = parser.parse_args()

    input_apk = args.input_apk

    base, ext = os.path.splitext(input_apk)
    debuggable_apk = f"{base}_debuggable{ext}"
    aligned_debuggable_apk = f"{base}_aligned_debuggable{ext}"

    # Construct the commands
    command1 = (
        f'{java_path} -jar {manifest_editor_jar} "{input_apk}" '
        f'-o "{debuggable_apk}" -d 1'
    )
    command2 = (
        f'{zipalign_path} 4 "{debuggable_apk}" "{aligned_debuggable_apk}"'
    )
    command3 = (
        f'{java_path} -jar {apksigner_jar} sign '
        f'--v1-signing-enabled --v2-signing-enabled '
        f'--ks {keystore_path} --ks-pass pass:xxx '
        f'"{aligned_debuggable_apk}"'
    )

    try:
        print("Running Command 1: Modifying APK...")
        subprocess.run(command1, shell=True, check=True)

        print("Running Command 2: Aligning APK...")
        subprocess.run(command2, shell=True, check=True)

        print("Running Command 3: Signing APK...")
        subprocess.run(command3, shell=True, check=True)

        if os.path.exists(debuggable_apk):
            os.remove(debuggable_apk)
            print(f"Deleted intermediate APK file: {debuggable_apk}")

        print("All commands executed successfully!")
    except subprocess.CalledProcessError as e:
        print("An error occurred while running one of the commands:")
        print(e)

if __name__ == "__main__":
    main()
