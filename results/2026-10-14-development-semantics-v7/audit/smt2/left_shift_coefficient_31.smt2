(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x324 (bvmul x (_ bv2147483648 32))))
(let ((?x322 (bvshl x (_ bv31 32))))
(and (distinct ?x322 ?x324) true))))
(check-sat)
