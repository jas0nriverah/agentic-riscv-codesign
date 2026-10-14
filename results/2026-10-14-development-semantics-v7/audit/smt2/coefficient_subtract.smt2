(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(declare-fun b () (_ BitVec 32))
(declare-fun a () (_ BitVec 32))
(assert
 (let ((?x38 (bvmul (bvsub a b) x)))
(let ((?x32 (bvmul b x)))
(let ((?x31 (bvmul a x)))
(let ((?x36 (bvsub ?x31 ?x32)))
(and (distinct ?x36 ?x38) true))))))
(check-sat)
