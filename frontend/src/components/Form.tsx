"use client";
import React,{useState} from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import axios from "axios";
import {repoAnalysisRoute, repoVerifyRoute } from "@/utils/APIRoutes";
import { v4 as uuidv4 } from "uuid";


type FormProps = {
  setParentLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setParentRequestId: (id: string) => void;
};


export function Form({ setParentLoading, setParentRequestId }:FormProps) {
    const [repoUrl, setRepoUrl] = useState<string>("");
    const [branch, setBranch] = useState<string>("");
    const [loading,setLoading] = useState<boolean>(false);
    const [analyzing, setAnalyzing] = useState<boolean>(false);
    const [errorMessage,setErrorMessage] = useState<string>("") 
    const [verifyMessage,setVerifyMessage] = useState<string>("Verify")
    const [isVerified,setIsVerified] = useState<boolean>(false);

  const verifyRepo = async () => {
    setErrorMessage(""); // reset previous error
    console.log("[DEBUG] Verify button clicked");
    
    if (!repoUrl || !branch) {
      setErrorMessage("Please enter both repository URL and branch.");
      console.log("[DEBUG] Verify failed: missing URL or branch");
      return;
    }

    console.log("[DEBUG] Verifying repo:", { repoUrl, branch });
    setLoading(true);
    setVerifyMessage("Verifying")
    try {
      console.log("[DEBUG] Calling /api/verify endpoint");
      const response = await axios.post(repoVerifyRoute, {
        repo_url: repoUrl,
        branch: branch,
      });

      console.log("[DEBUG] Verify response:", response.data);

      if (response.data.success) {
        setVerifyMessage("Verified")
        setIsVerified(true)
        console.log("[DEBUG] Verification successful");
      } else {
        setVerifyMessage("Verify")
        setErrorMessage(response.data.error || "Verification failed.");
        console.log("[DEBUG] Verification failed:", response.data.error);
      }
    } catch (error) {
        console.error("[DEBUG] Verification API error:", error);
        setVerifyMessage("Verify");
        setErrorMessage("Something went wrong during verification.");
    } finally {
      setLoading(false);
    }
  };



  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage(""); // reset previous error
    console.log("[DEBUG] Form submitted");
    
    if(!isVerified){
        setErrorMessage("Please verify the repository before analyzing.");
        console.log("[DEBUG] Form not verified");
        return
    }
    const requestId = uuidv4();
    console.log("[DEBUG] Submitting analyze request with:", { repoUrl, branch, requestId });
    
    setAnalyzing(true);
    setParentLoading(true);
    setParentRequestId(requestId)
    try{
      console.log("[DEBUG] Calling /api/analyze endpoint");
      const response = await axios.post(repoAnalysisRoute, {
        repo_url:repoUrl,
        branch:branch,
        request_id: requestId,
      });
      
      console.log("[DEBUG] /api/analyze response:", response.data);
      
      if (response.data.error) {
        setErrorMessage(`Error: ${response.data.error}`);
        setAnalyzing(false);
        setParentLoading(false);
        console.log("[DEBUG] Error from API:", response.data.error);
        return; 
      }
      console.log("[DEBUG] Analysis queued successfully, showing loading screen");
      // Don't redirect here - let LoadingScreen handle redirecting after analysis completes
    }catch(error){
      console.error("[DEBUG] API error:", error);
      setErrorMessage("Something went wrong during analysis.");
      setAnalyzing(false);
      setParentLoading(false);
    }
  };

  return (
    <div className="shadow-input mx-auto w-full max-w-md rounded-none   md:rounded-2xl p-4 ">
      <form className="" onSubmit={onSubmit}>
        <LabelInputContainer className="mb-4">
          <Label htmlFor="repo_url">Repository</Label>
          <Input id="repo_url" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="Enter a repo URL"  />
        </LabelInputContainer>
        <div className="mb-4 flex flex-col space-y-2 md:flex-row md:space-y-0 md:space-x-2">
          <LabelInputContainer>
            <Label htmlFor="branch">Branch</Label>
            <Input id="branch" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="Enter a branch" type="text" />
          </LabelInputContainer>
          <button type="button" onClick={verifyRepo} disabled={loading} className="relative w-full mt-6 inline-flex h-10 overflow-hidden rounded-full p-px focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:ring-offset-slate-50">
            <span className="absolute inset-[-1000%] animate-[spin_2s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#E2CBFF_0%,#393BB2_50%,#E2CBFF_100%)]" />
            <span className="inline-flex h-full w-full cursor-pointer items-center justify-center rounded-full bg-slate-950 px-3 py-1 text-sm font-medium text-white backdrop-blur-3xl">
                {verifyMessage}
            </span>
            </button>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <p className="text-red-600 text-sm mb-4">{errorMessage}</p>
        )}

        <button type="submit" disabled={loading || analyzing} className="shadow-[inset_0_0_0_2px_#616467] w-full text-black px-12 py-4 rounded-full tracking-widest uppercase font-bold bg-transparent hover:bg-[#616467] hover:text-white dark:text-neutral-200 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed">
            {analyzing ? 'Analyzing...' : 'Analyze'}
        </button>
        
      </form>
    </div>
  );
}



const LabelInputContainer = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn("flex w-full flex-col space-y-2", className)}>
      {children}
    </div>
  );
};


