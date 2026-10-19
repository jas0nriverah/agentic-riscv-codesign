(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x66 (bvmul x (_ bv4 32))))
(let ((?x64 (bvshl x (_ bv2 32))))
(and (distinct ?x64 ?x66) true))))
(check-sat)
