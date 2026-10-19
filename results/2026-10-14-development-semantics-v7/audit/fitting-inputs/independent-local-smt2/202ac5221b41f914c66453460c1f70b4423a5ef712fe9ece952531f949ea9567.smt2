(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x402 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv4294770688 32))))
(let ((?x1210 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x98 (bvshl (bvadd independent_opaque_0 (_ bv4294967293 32)) ?x1210)))
(and (distinct ?x98 ?x402) true)))))
(check-sat)
