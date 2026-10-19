(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(declare-fun b () (_ BitVec 32))
(declare-fun a () (_ BitVec 32))
(assert
 (let ((?x44 (bvmul (bvmul a b) x)))
(let ((?x32 (bvmul b x)))
(let ((?x42 (bvmul a ?x32)))
(and (distinct ?x42 ?x44) true)))))
(check-sat)
