(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x172 (bvmul x (_ bv16384 32))))
(let ((?x170 (bvshl x (_ bv14 32))))
(and (distinct ?x170 ?x172) true))))
(check-sat)
